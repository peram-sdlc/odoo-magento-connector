import os

import requests
from requests.compat import urlparse, urlunparse
from requests.utils import quote

class MagentoAPI:
    def __init__(self, instance):
        self.instance = instance
        self.base_url = instance.base_url.rstrip("/")
        self._store_code = None
        self._guest_cart_rest_prefix = "/rest/V1"
        self.headers = {"Content-Type": "application/json"}
        access_token = getattr(instance, "access_token", None)
        if isinstance(access_token, str):
            access_token = access_token.strip()
        if access_token:
            self.headers["Authorization"] = f"Bearer {access_token}"

        self.verify = bool(instance.verify_ssl)
        self._container_gateway_ip = self._detect_container_gateway_ip()
        self._base_urls = self._build_base_urls()

    def _is_containerized_runtime(self):
        # Docker/Podman usually expose one of these markers in Linux containers.
        if os.path.exists("/.dockerenv") or os.path.exists("/run/.containerenv"):
            return True
        try:
            with open("/proc/1/cgroup", "r", encoding="utf-8") as handle:
                data = handle.read().lower()
            return any(token in data for token in ("docker", "podman", "containerd", "kubepods"))
        except OSError:
            return False

    def _detect_container_gateway_ip(self):
        if not self._is_containerized_runtime():
            return None

        # Resolve the container default gateway from /proc/net/route.
        try:
            with open("/proc/net/route", "r", encoding="utf-8") as handle:
                for line in handle.readlines()[1:]:
                    parts = line.strip().split()
                    if len(parts) < 3:
                        continue
                    destination = parts[1]
                    gateway_hex = parts[2]
                    if destination != "00000000" or gateway_hex == "00000000":
                        continue
                    try:
                        octets = [str(int(gateway_hex[idx:idx + 2], 16)) for idx in (6, 4, 2, 0)]
                    except ValueError:
                        return None
                    return ".".join(octets)
        except OSError:
            return None
        return None

    def _build_base_urls(self):
        base_urls = [self.base_url]
        parsed = urlparse(self.base_url)
        host = (parsed.hostname or "").strip().lower()
        if host not in {"localhost", "127.0.0.1", "::1"}:
            return base_urls

        # Only add container-to-host fallbacks when Odoo itself runs in a container.
        if not self._is_containerized_runtime():
            return base_urls

        # Keep localhost usable in common deployment layouts:
        # - native host: localhost / 127.0.0.1 / ::1
        # - docker/podman container -> host machine:
        #   host.docker.internal / host.containers.internal / gateway.docker.internal
        # - container default gateway detected from /proc/net/route
        shared_fallback_hosts = [
            "host.docker.internal",
            "host.containers.internal",
            "gateway.docker.internal",
        ]
        if self._container_gateway_ip:
            shared_fallback_hosts.append(self._container_gateway_ip)

        fallback_hosts = {
            "localhost": [
                "127.0.0.1",
                "::1",
                *shared_fallback_hosts,
            ],
            "127.0.0.1": [
                "localhost",
                "::1",
                *shared_fallback_hosts,
            ],
            "::1": [
                "localhost",
                "127.0.0.1",
                *shared_fallback_hosts,
            ],
        }.get(host, [])

        auth = ""
        if parsed.username:
            auth = parsed.username
            if parsed.password is not None:
                auth += f":{parsed.password}"
            auth += "@"
        port = f":{parsed.port}" if parsed.port else ""

        for fallback_host in fallback_hosts:
            netloc_host = fallback_host
            if ":" in netloc_host and not netloc_host.startswith("["):
                netloc_host = f"[{netloc_host}]"
            fallback_netloc = f"{auth}{netloc_host}{port}"
            fallback_url = urlunparse(
                (parsed.scheme, fallback_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
            ).rstrip("/")
            if fallback_url not in base_urls:
                base_urls.append(fallback_url)
        return base_urls

    def _is_loopback_base_url(self, base_url):
        host = (urlparse(base_url).hostname or "").strip().lower()
        return host in {"localhost", "127.0.0.1", "::1"}

    def _is_localhost_related_base_url(self, base_url):
        host = (urlparse(base_url).hostname or "").strip().lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True

        original_host = (urlparse(self.base_url).hostname or "").strip().lower()
        if original_host not in {"localhost", "127.0.0.1", "::1"}:
            return False

        localhost_related_hosts = {
            "host.docker.internal",
            "host.containers.internal",
            "gateway.docker.internal",
        }
        if self._container_gateway_ip:
            localhost_related_hosts.add(self._container_gateway_ip)
        return host in localhost_related_hosts

    def _request(self, method, endpoint, *, params=None, payload=None):
        last_exc = None
        primary_exc = None
        for base_url in self._base_urls:
            request_kwargs = {
                "headers": self.headers,
                "timeout": 60,
                "verify": self.verify,
            }
            if params is not None:
                request_kwargs["params"] = params
            if payload is not None:
                request_kwargs["json"] = payload
            url = f"{base_url}{endpoint}"

            try:
                response = requests.request(method, url, **request_kwargs)
                response.raise_for_status()
                return response
            except requests.exceptions.SSLError as exc:
                # Local Magento often uses self-signed certs; retry loopback once without SSL verify.
                if self.verify and self._is_localhost_related_base_url(base_url):
                    retry_kwargs = dict(request_kwargs)
                    retry_kwargs["verify"] = False
                    try:
                        response = requests.request(method, url, **retry_kwargs)
                        response.raise_for_status()
                        return response
                    except requests.exceptions.RequestException as retry_exc:
                        if base_url == self.base_url and primary_exc is None:
                            primary_exc = retry_exc
                        last_exc = retry_exc
                        continue
                if base_url == self.base_url and primary_exc is None:
                    primary_exc = exc
                last_exc = exc
                continue
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
                if base_url == self.base_url and primary_exc is None:
                    primary_exc = exc
                last_exc = exc
                continue

        if primary_exc is not None:
            raise primary_exc
        if last_exc is not None:
            raise last_exc
        raise requests.exceptions.RequestException("Magento request failed without response.")

    def _get(self, endpoint, params=None):
        response = self._request("get", endpoint, params=params)
        return response.json()

    def _post(self, endpoint, payload=None):
        response = self._request("post", endpoint, payload=payload)
        return response.json()

    def _put(self, endpoint, payload=None):
        response = self._request("put", endpoint, payload=payload)
        return response.json()

    def _resolve_store_code(self):
        if self._store_code is not None:
            return self._store_code

        self._store_code = ""
        explicit_code = str(getattr(self.instance, "store_code", "") or "").strip()
        if explicit_code:
            self._store_code = explicit_code
            return self._store_code

        try:
            store_id = int(getattr(self.instance, "store_id", 0) or 0)
        except (TypeError, ValueError):
            store_id = 0
        if not store_id:
            return self._store_code

        try:
            store_configs = self.get_store_configs() or []
        except Exception:
            return self._store_code

        for config in store_configs:
            candidate_id = config.get("id")
            if candidate_id is None:
                candidate_id = config.get("store_id")
            try:
                candidate_id = int(candidate_id)
            except (TypeError, ValueError):
                continue
            if candidate_id != store_id:
                continue
            code = (config.get("code") or config.get("store_code") or "").strip()
            if code:
                self._store_code = code
                break
        return self._store_code

    def _get_store_rest_prefix(self):
        store_code = self._resolve_store_code()
        if store_code:
            return f"/rest/{quote(store_code, safe='')}/V1"
        return "/rest/V1"

    def _guest_cart_endpoint(self, suffix=""):
        suffix = str(suffix or "")
        if suffix and not suffix.startswith("/"):
            suffix = "/" + suffix
        return f"{self._guest_cart_rest_prefix}/guest-carts{suffix}"

    def _rest_prefix_candidates(self, include_all_scope=False):
        prefixes = []
        if include_all_scope:
            prefixes.append("/rest/all/V1")
        store_prefix = self._get_store_rest_prefix()
        if store_prefix:
            prefixes.append(store_prefix)
        prefixes.append("/rest/V1")
        unique = []
        seen = set()
        for prefix in prefixes:
            if prefix in seen:
                continue
            seen.add(prefix)
            unique.append(prefix)
        return unique

    def _request_with_prefix_fallback(
        self,
        method,
        endpoint_builder,
        *,
        include_all_scope=False,
        payload=None,
        params=None,
    ):
        last_exc = None
        prefixes = self._rest_prefix_candidates(include_all_scope=include_all_scope)
        for idx, prefix in enumerate(prefixes):
            endpoint = endpoint_builder(prefix)
            try:
                if method == "get":
                    return self._get(endpoint, params=params)
                if method == "post":
                    return self._post(endpoint, payload)
                if method == "put":
                    return self._put(endpoint, payload)
                raise ValueError(f"Unsupported HTTP method: {method}")
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                can_retry = idx < (len(prefixes) - 1) and status in (400, 401, 403, 404)
                if can_retry:
                    last_exc = exc
                    continue
                raise
        if last_exc:
            raise last_exc
        raise requests.exceptions.HTTPError("Magento request failed without HTTP response.")

    def get_store_configs(self):
        return self._get("/rest/V1/store/storeConfigs")

    def get_websites(self):
        return self._get("/rest/V1/store/websites")

    def get_products(self):
        response = self._request_with_prefix_fallback(
            "get",
            lambda prefix: f"{prefix}/products",
            include_all_scope=True,
            params={"searchCriteria": ""},
        )
        if isinstance(response, dict):
            return response.get("items", [])
        return []

    def _search_products(self, params):
        response = self._request_with_prefix_fallback(
            "get",
            lambda prefix: f"{prefix}/products",
            include_all_scope=True,
            params=params,
        )
        if isinstance(response, dict):
            return response.get("items", [])
        return []

    def get_product_by_id(self, product_id):
        try:
            pid = int(product_id)
        except (TypeError, ValueError):
            return {}

        filter_templates = (
            {"field": "id", "value": str(pid), "condition_type": "eq"},
            {"field": "entity_id", "value": str(pid), "condition_type": "eq"},
        )
        for flt in filter_templates:
            params = {
                "searchCriteria[filter_groups][0][filters][0][field]": flt["field"],
                "searchCriteria[filter_groups][0][filters][0][value]": flt["value"],
                "searchCriteria[filter_groups][0][filters][0][condition_type]": flt["condition_type"],
            }
            try:
                items = self._search_products(params)
            except requests.exceptions.HTTPError:
                items = []
            if items:
                return items[0]
        return {}

    def get_attribute_sets(self):
        return self._get(
            "/rest/V1/products/attribute-sets/sets/list",
            params={"searchCriteria": ""},
        ).get("items", [])

    def create_attribute_set(self, name, skeleton_id=4):
        payload = {
            "attributeSet": {
                "attribute_set_name": name,
                "sort_order": 0,
            },
            "skeletonId": int(skeleton_id),
        }
        return self._post("/rest/V1/products/attribute-sets", payload)

    def update_attribute_set(self, attribute_set_id, name):
        payload = {
            "attributeSet": {
                "attribute_set_id": int(attribute_set_id),
                "attribute_set_name": name,
            }
        }
        return self._put(f"/rest/V1/products/attribute-sets/{attribute_set_id}", payload)

    def get_orders(self):
        return self._get("/rest/V1/orders", params={"searchCriteria": ""}).get("items", [])

    def get_order(self, order_id):
        return self._get(f"/rest/V1/orders/{order_id}")

    def get_order_transactions(self, order_id):
        payload = self._get(f"/rest/V1/orders/{order_id}/transactions")
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                return items
            transactions = payload.get("transactions")
            if isinstance(transactions, list):
                return transactions
        return []

    def get_invoices(self, order_id=None):
        if order_id:
            params = {
                "searchCriteria[filter_groups][0][filters][0][field]": "order_id",
                "searchCriteria[filter_groups][0][filters][0][value]": str(order_id),
                "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            }
        else:
            params = {"searchCriteria": ""}
        return self._get("/rest/V1/invoices", params=params).get("items", [])

    def get_invoice(self, invoice_id):
        return self._get(f"/rest/V1/invoices/{invoice_id}")

    def get_credit_memos(self, order_id=None):
        if order_id:
            params = {
                "searchCriteria[filter_groups][0][filters][0][field]": "order_id",
                "searchCriteria[filter_groups][0][filters][0][value]": str(order_id),
                "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            }
        else:
            params = {"searchCriteria": ""}
        return self._get("/rest/V1/creditmemos", params=params).get("items", [])

    def get_credit_memo(self, credit_memo_id):
        return self._get(f"/rest/V1/creditmemo/{credit_memo_id}")

    def get_shipments(self, order_id=None):
        if order_id:
            params = {
                "searchCriteria[filter_groups][0][filters][0][field]": "order_id",
                "searchCriteria[filter_groups][0][filters][0][value]": str(order_id),
                "searchCriteria[filter_groups][0][filters][0][condition_type]": "eq",
            }
        else:
            params = {"searchCriteria": ""}
        return self._get("/rest/V1/shipments", params=params).get("items", [])

    def get_shipment(self, shipment_id):
        return self._get(f"/rest/V1/shipment/{shipment_id}")

    def create_order(self, payload):
        return self._post("/rest/V1/orders", payload)

    def update_order(self, order_id, payload):
        return self._put(f"/rest/V1/orders/{order_id}", payload)

    def create_invoice(self, order_id, payload):
        return self._post(f"/rest/V1/order/{order_id}/invoice", payload)

    def create_credit_memo(self, order_id, payload):
        return self._post(f"/rest/V1/order/{order_id}/refund", payload)

    def create_shipment(self, order_id, payload):
        return self._post(f"/rest/V1/order/{order_id}/ship", payload)

    def create_guest_cart(self):
        store_prefix = self._get_store_rest_prefix()
        if store_prefix != "/rest/V1":
            try:
                self._guest_cart_rest_prefix = store_prefix
                return self._post(f"{store_prefix}/guest-carts")
            except requests.exceptions.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else 0
                if status not in (400, 404):
                    raise
        self._guest_cart_rest_prefix = "/rest/V1"
        return self._post("/rest/V1/guest-carts")

    def add_guest_cart_item(self, cart_id, sku, qty):
        payload = {
            "cartItem": {
                "quote_id": cart_id,
                "sku": sku,
                "qty": qty,
            }
        }
        return self._post(self._guest_cart_endpoint(f"{cart_id}/items"), payload)

    def set_guest_shipping_information(self, cart_id, payload):
        return self._post(self._guest_cart_endpoint(f"{cart_id}/shipping-information"), payload)

    def set_guest_payment_information(self, cart_id, payload):
        return self._post(self._guest_cart_endpoint(f"{cart_id}/payment-information"), payload)

    def get_categories(self):
        return self._get("/rest/V1/categories")

    def get_category(self, category_id):
        return self._get(f"/rest/V1/categories/{category_id}")

    def create_category(self, payload):
        return self._post("/rest/V1/categories", payload)

    def update_category(self, category_id, payload):
        return self._put(f"/rest/V1/categories/{category_id}", payload)

    def get_product(self, sku):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._request_with_prefix_fallback(
            "get",
            lambda prefix: f"{prefix}/products/{safe_sku}",
            include_all_scope=True,
        )

    def create_product(self, payload):
        return self._request_with_prefix_fallback(
            "post",
            lambda prefix: f"{prefix}/products",
            include_all_scope=True,
            payload=payload,
        )

    def update_product(self, sku, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._request_with_prefix_fallback(
            "put",
            lambda prefix: f"{prefix}/products/{safe_sku}",
            include_all_scope=True,
            payload=payload,
        )

    def make_product_saleable_for_cart(self, sku, qty=0.0):
        sku_value = str(sku or "").strip()
        if not sku_value:
            return False

        product = self.get_product(sku_value) or {}
        stock_item = ((product.get("extension_attributes") or {}).get("stock_item") or {})

        try:
            current_qty = float(stock_item.get("qty") or 0.0)
        except (TypeError, ValueError):
            current_qty = 0.0
        try:
            requested_qty = float(qty or 0.0)
        except (TypeError, ValueError):
            requested_qty = 0.0

        target_qty = max(current_qty, requested_qty, 1.0)
        payload = {
            "product": {
                "sku": sku_value,
                "extension_attributes": {
                    "stock_item": {
                        "qty": target_qty,
                        "is_in_stock": True,
                        "use_config_manage_stock": False,
                        "manage_stock": False,
                        "use_config_backorders": False,
                        "backorders": 1,
                    }
                },
            }
        }
        self.update_product(sku_value, payload)
        return True

    def add_product_media(self, sku, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._request_with_prefix_fallback(
            "post",
            lambda prefix: f"{prefix}/products/{safe_sku}/media",
            include_all_scope=True,
            payload=payload,
        )

    def update_product_media(self, sku, entry_id, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._request_with_prefix_fallback(
            "put",
            lambda prefix: f"{prefix}/products/{safe_sku}/media/{entry_id}",
            include_all_scope=True,
            payload=payload,
        )

    def get_product_media(self, sku, entry_id):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._request_with_prefix_fallback(
            "get",
            lambda prefix: f"{prefix}/products/{safe_sku}/media/{entry_id}",
            include_all_scope=True,
        )

    def get_customers(self):
        return self._get("/rest/V1/customers/search", params={"searchCriteria": ""}).get("items", [])

    def get_customer(self, customer_id):
        return self._get(f"/rest/V1/customers/{customer_id}")

    def create_customer(self, payload):
        return self._post("/rest/V1/customers", payload)

    def update_customer(self, customer_id, payload):
        return self._put(f"/rest/V1/customers/{customer_id}", payload)

    def get_country(self, country_code):
        safe_code = quote(str(country_code or "").strip(), safe="")
        return self._get(f"/rest/V1/directory/countries/{safe_code}")

    # ---------------- Tax classes ----------------
    def get_tax_classes(self):
        # Magento returns CUSTOMER and PRODUCT classes via taxClasses/search.
        params = {
            "searchCriteria[filter_groups][0][filters][0][field]": "class_type",
            "searchCriteria[filter_groups][0][filters][0][value]": "PRODUCT,CUSTOMER",
            "searchCriteria[filter_groups][0][filters][0][condition_type]": "in",
        }
        try:
            payload = self._get("/rest/V1/taxClasses/search", params=params)
        except requests.exceptions.HTTPError:
            payload = self._get("/rest/V1/taxClasses/search", params={"searchCriteria": ""})
        if isinstance(payload, dict):
            return payload.get("items", []) or []
        return []

    # ---------------- MSI / Inventory ----------------
    def get_inventory_sources(self):
        payload = self._get("/rest/V1/inventory/sources", params={"searchCriteria": ""})
        if isinstance(payload, dict):
            return payload.get("items", []) or []
        return []

    def get_inventory_stocks(self):
        payload = self._get("/rest/V1/inventory/stocks", params={"searchCriteria": ""})
        if isinstance(payload, dict):
            return payload.get("items", []) or []
        return []

    def get_source_items(self, sku=None, source_code=None):
        params = {"searchCriteria": ""}
        idx = 0
        if sku:
            params[f"searchCriteria[filter_groups][{idx}][filters][0][field]"] = "sku"
            params[f"searchCriteria[filter_groups][{idx}][filters][0][value]"] = sku
            params[f"searchCriteria[filter_groups][{idx}][filters][0][condition_type]"] = "eq"
            idx += 1
        if source_code:
            params[f"searchCriteria[filter_groups][{idx}][filters][0][field]"] = "source_code"
            params[f"searchCriteria[filter_groups][{idx}][filters][0][value]"] = source_code
            params[f"searchCriteria[filter_groups][{idx}][filters][0][condition_type]"] = "eq"
        payload = self._get("/rest/V1/inventory/source-items", params=params)
        if isinstance(payload, dict):
            return payload.get("items", []) or []
        return []

    def update_source_items(self, source_items):
        """source_items: list of {sku, source_code, quantity, status}."""
        if not source_items:
            return {}
        return self._post(
            "/rest/V1/inventory/source-items",
            {"sourceItems": source_items},
        )

    # ---------------- Customer Groups ----------------
    def get_customer_groups(self):
        payload = self._get("/rest/V1/customerGroups/search", params={"searchCriteria": ""})
        if isinstance(payload, dict):
            return payload.get("items", []) or []
        return []
