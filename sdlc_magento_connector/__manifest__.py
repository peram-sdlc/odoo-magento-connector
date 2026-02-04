{
    'name': 'SDLC Magento 2 Connector',
    'version': '1.0',
    'category': 'Connector',
    'summary': 'Magento 2 Connector for Odoo',
    'author': 'SDLC Corp',
    'depends': ['base', 'product', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/magento_instance_views.xml',
        'data/cron.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': True,
}
