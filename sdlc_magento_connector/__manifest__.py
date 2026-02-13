{
    'name': 'SDLC Magento 2 Connector',
    'version': '1.0',
    'category': 'Connector',
    'summary': 'Magento 2 Connector for Odoo',
    'author': 'SDLC Corp',
    'depends': ['base', 'product', 'sale', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/cleanup_billing_agreement.xml',
        'views/magento_sale_order_view.xml',
        'views/magento_stock_picking_view.xml',
        'views/magento_field_mapping_views.xml',
        'views/magento_instance_views.xml',
        'views/account_move_form_magento.xml',
        'data/cron.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'sdlc_magento_connector/static/src/js/magento_dashboard.js',
            'sdlc_magento_connector/static/src/scss/magento_dashboard.scss',
            'sdlc_magento_connector/static/src/xml/magento_dashboard.xml',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
}
