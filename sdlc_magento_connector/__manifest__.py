{
    'name': 'SDLC Magento 2 Connector',
    'version': '1.0',
    'category': 'Connector',
    'summary': 'Magento 2 Connector for Odoo',
    'author': 'SDLC Corp',
    'depends': ['base', 'product', 'sale', 'account', 'sdlc_shopify_connector'],
    'data': [
        'security/ir.model.access.csv',
        'views/magento_sale_order_view.xml',
        'views/magento_stock_picking_view.xml',
        'views/magento_instance_views.xml',
        'data/cron.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
}
