import requests
from requests.utils import quote
from requests_oauthlib import OAuth1

class MagentoAPI:
    def __init__(self, instance):
        self.instance = instance
        self.base_url = instance.base_url.rstrip("/")
        self.auth = None
        consumer_key = getattr(instance, "consumer_key", None) or getattr(instance, "oauth_consumer_key", None)
        consumer_secret = getattr(instance, "consumer_secret", None) or getattr(instance, "oauth_consumer_secret", None)
        access_token = getattr(instance, "access_token", None)
        access_token_secret = (
            getattr(instance, "access_token_secret", None)
            or getattr(instance, "oauth_access_token_secret", None)
            or getattr(instance, "oauth_token_secret", None)
        )

        if consumer_key and consumer_secret and access_token and access_token_secret:
            signature_method = (
                getattr(instance, "oauth_signature_method", None)
                or getattr(instance, "signature_method", None)
                or "HMAC-SHA256"
            )
            signature_type = (
                getattr(instance, "oauth_signature_type", None)
                or getattr(instance, "signature_type", None)
                or "QUERY"
            )
            self.auth = OAuth1(
                consumer_key,
                consumer_secret,
                access_token,
                access_token_secret,
                signature_method=signature_method,
                signature_type=signature_type,
            )
            self.headers = {"Content-Type": "application/json"}
        else:
            self.headers = {
                "Authorization": f"Bearer {instance.access_token}",
                "Content-Type": "application/json",
            }

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
            auth=self.auth,
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
            auth=self.auth,
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
            auth=self.auth,
            verify=self.verify,
        )
        response.raise_for_status()
        return response.json()

    def get_store_configs(self):
        return self._get("/rest/V1/store/storeConfigs")

    def get_websites(self):
        return self._get("/rest/V1/store/websites")

    def get_products(self):
        return self._get("/rest/V1/products", params={"searchCriteria": ""}).get("items", [])

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
        return self._post("/rest/V1/guest-carts")

    def add_guest_cart_item(self, cart_id, sku, qty):
        payload = {
            "cartItem": {
                "quote_id": cart_id,
                "sku": sku,
                "qty": qty,
            }
        }
        return self._post(f"/rest/V1/guest-carts/{cart_id}/items", payload)

    def set_guest_shipping_information(self, cart_id, payload):
        return self._post(f"/rest/V1/guest-carts/{cart_id}/shipping-information", payload)

    def set_guest_payment_information(self, cart_id, payload):
        return self._post(f"/rest/V1/guest-carts/{cart_id}/payment-information", payload)

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
        return self._get(f"/rest/V1/products/{safe_sku}")

    def create_product(self, payload):
        return self._post("/rest/V1/products", payload)

    def update_product(self, sku, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._put(f"/rest/V1/products/{safe_sku}", payload)

    def add_product_media(self, sku, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._post(f"/rest/V1/products/{safe_sku}/media", payload)

    def update_product_media(self, sku, entry_id, payload):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._put(f"/rest/V1/products/{safe_sku}/media/{entry_id}", payload)

    def get_product_media(self, sku, entry_id):
        safe_sku = quote(str(sku or "").strip(), safe="")
        return self._get(f"/rest/V1/products/{safe_sku}/media/{entry_id}")

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
    
    def get_websites(self):
        return self._get("/rest/V1/store/websites")
