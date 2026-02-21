import requests
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

        if instance.verify_ssl:
            self.verify = r"C:\Users\Admin\AppData\Local\mkcert\rootCA.pem"
        else:
            self.verify = False  

    def _get(self, endpoint, params=None):
        response = requests.get(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            params=params,
            timeout=60,
            verify=self.verify,
        )
        response.raise_for_status()
        return response.json()

    def _post(self, endpoint, payload=None):
        response = requests.post(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            json=payload,
            timeout=60,
            verify=self.verify,
        )
        response.raise_for_status()
        return response.json()

    def _put(self, endpoint, payload=None):
        response = requests.put(
            f"{self.base_url}{endpoint}",
            headers=self.headers,
            json=payload,
            timeout=60,
            verify=self.verify,
        )
        response.raise_for_status()
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
