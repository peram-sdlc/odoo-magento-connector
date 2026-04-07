"""
Generate SDLC Magento 2 Connector - User Guide PDF
Run: python _generate_user_guide.py
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable,
)
import os

OUTPUT = os.path.join(os.path.dirname(__file__), 'SDLC_Magento2_Connector_User_Guide.pdf')

# Colors - Magento orange theme
PRIMARY = HexColor('#ff6d00')
PRIMARY_DARK = HexColor('#e65100')
SECONDARY = HexColor('#6a3093')
ACCENT_GREEN = HexColor('#4caf50')
DARK = HexColor('#1a1a2e')
MUTED = HexColor('#7a7a8a')
TABLE_HEADER = HexColor('#ff6d00')
TABLE_ALT = HexColor('#fff8f0')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle('CoverTitle', parent=styles['Title'], fontSize=32, textColor=PRIMARY_DARK, spaceAfter=10, alignment=TA_CENTER, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('CoverSub', parent=styles['Normal'], fontSize=14, textColor=MUTED, alignment=TA_CENTER, spaceAfter=6))
styles.add(ParagraphStyle('H1', parent=styles['Heading1'], fontSize=22, textColor=PRIMARY_DARK, spaceBefore=20, spaceAfter=12, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('H2', parent=styles['Heading2'], fontSize=16, textColor=SECONDARY, spaceBefore=16, spaceAfter=8, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('H3', parent=styles['Heading3'], fontSize=13, textColor=DARK, spaceBefore=12, spaceAfter=6, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('Body', parent=styles['Normal'], fontSize=10.5, textColor=DARK, spaceAfter=6, leading=15, alignment=TA_JUSTIFY))
styles.add(ParagraphStyle('BodyBold', parent=styles['Normal'], fontSize=10.5, textColor=DARK, spaceAfter=6, leading=15, fontName='Helvetica-Bold'))
styles.add(ParagraphStyle('BulletItem', parent=styles['Normal'], fontSize=10.5, textColor=DARK, spaceAfter=4, leading=14, leftIndent=20, bulletIndent=8))
styles.add(ParagraphStyle('Note', parent=styles['Normal'], fontSize=10, textColor=HexColor('#1565c0'), spaceAfter=8, leading=14, leftIndent=10, borderColor=HexColor('#bbdefb'), borderWidth=1, borderPadding=8, backColor=HexColor('#e3f2fd')))
styles.add(ParagraphStyle('Tip', parent=styles['Normal'], fontSize=10, textColor=HexColor('#2e7d32'), spaceAfter=8, leading=14, leftIndent=10, borderColor=HexColor('#c8e6c9'), borderWidth=1, borderPadding=8, backColor=HexColor('#e8f5e9')))
styles.add(ParagraphStyle('Warning', parent=styles['Normal'], fontSize=10, textColor=HexColor('#c62828'), spaceAfter=8, leading=14, leftIndent=10, borderColor=HexColor('#ffcdd2'), borderWidth=1, borderPadding=8, backColor=HexColor('#ffebee')))
styles.add(ParagraphStyle('TOCEntry', parent=styles['Normal'], fontSize=11, textColor=DARK, spaceAfter=5, leftIndent=10, leading=16))


def tbl(headers, rows, col_widths=None):
    data = [headers] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    s = [('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER), ('TEXTCOLOR', (0, 0), (-1, 0), white),
         ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 10),
         ('FONTSIZE', (0, 1), (-1, -1), 9.5), ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
         ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#ffe0b2')),
         ('TOPPADDING', (0, 0), (-1, -1), 6), ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
         ('LEFTPADDING', (0, 0), (-1, -1), 8), ('RIGHTPADDING', (0, 0), (-1, -1), 8)]
    for i in range(1, len(data)):
        if i % 2 == 0:
            s.append(('BACKGROUND', (0, i), (-1, i), TABLE_ALT))
    t.setStyle(TableStyle(s))
    return t


def hr():
    return HRFlowable(width='100%', thickness=1, color=HexColor('#ffe0b2'), spaceBefore=8, spaceAfter=8)


def B(items):
    """Render bullet list."""
    r = []
    for i in items:
        r.append(Paragraph(i, styles['BulletItem'], bulletText='\u2022'))
    return r


def build():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                            topMargin=2.5*cm, bottomMargin=2*cm,
                            title='SDLC Magento 2 Connector - User Guide', author='SDLC Corp')
    S = []

    # ===== COVER =====
    S.append(Spacer(1, 60))
    S.append(Paragraph('SDLC Magento 2 Connector', styles['CoverTitle']))
    S.append(Paragraph('for Odoo 18', styles['CoverSub']))
    S.append(Spacer(1, 20))
    S.append(HRFlowable(width='60%', thickness=3, color=PRIMARY, spaceBefore=10, spaceAfter=10))
    S.append(Spacer(1, 20))
    S.append(Paragraph('User Guide', ParagraphStyle('x', parent=styles['CoverTitle'], fontSize=24, textColor=PRIMARY)))
    S.append(Spacer(1, 30))
    S.append(Paragraph('Version 1.0', styles['CoverSub']))
    S.append(Paragraph('Author: SDLC Corp', styles['CoverSub']))
    S.append(Paragraph('Module: sdlc_magento_connector', styles['CoverSub']))
    S.append(Spacer(1, 40))
    S.append(Paragraph(
        'A comprehensive guide to installing, configuring, and using the SDLC Magento 2 Connector '
        'module for bidirectional synchronization between Odoo 18 and Magento 2 stores.',
        ParagraphStyle('x', parent=styles['Body'], alignment=TA_CENTER, fontSize=11)))
    S.append(PageBreak())

    # ===== TOC =====
    S.append(Paragraph('Table of Contents', styles['H1']))
    S.append(hr())
    toc = [('1', 'Overview & Key Features'), ('2', 'Installation & Requirements'),
           ('3', 'Instance Configuration'), ('4', 'Dashboard'),
           ('5', 'Product Management'), ('6', 'Customer Management'),
           ('7', 'Order Management'), ('8', 'Invoice, Shipment & Credit Memos'),
           ('9', 'Field Mapping (Bidirectional)'), ('10', 'Auto Sync Cron Jobs'),
           ('11', 'Inventory Management'), ('12', 'Sync Reports & Logs'),
           ('13', 'Menu Structure'), ('14', 'Magento API Reference'),
           ('15', 'Troubleshooting'), ('16', 'FAQ')]
    for n, t in toc:
        S.append(Paragraph('%s.  %s' % (n, t), styles['TOCEntry']))
    S.append(PageBreak())

    # ===== 1. OVERVIEW =====
    S.append(Paragraph('1. Overview & Key Features', styles['H1']))
    S.append(hr())
    S.append(Paragraph(
        'The <b>SDLC Magento 2 Connector</b> provides deep, bidirectional integration between '
        'Odoo 18 and Magento 2 e-commerce stores. It synchronizes products, customers, orders, '
        'categories, invoices, shipments, and credit memos in real time.', styles['Body']))
    S.append(Paragraph('Key Features', styles['H2']))
    S.extend(B([
        '<b>Multi-Instance Support</b> - Connect multiple Magento 2 stores simultaneously',
        '<b>Bidirectional Field Mapping</b> - Map any Odoo field to any Magento API field including custom attributes',
        '<b>Real-time Dashboard</b> - KPIs, revenue charts, order status, top categories, top countries, sync health',
        '<b>Auto Sync Cron</b> - Schedule automatic sync (hourly/daily/weekly/monthly) per instance',
        '<b>Complete Order Lifecycle</b> - Orders, Invoices, Shipments, Credit Memos fully synced',
        '<b>Product Sync</b> - SKU-based mapping, images, stock, descriptions, categories, attribute sets',
        '<b>Customer Sync</b> - Full profile with addresses, gender, DOB, tax/VAT, groups',
        '<b>Inventory Tracking</b> - Real-time stock status sync between Magento and Odoo',
        '<b>Sync Reports</b> - Detailed audit trail of every sync operation',
        '<b>Guest Cart API</b> - Orders pushed via Magento cart API for proper workflow',
        '<b>Auto-Sync on Save</b> - Products, customers, orders auto-push on create/update',
    ]))
    S.append(PageBreak())

    # ===== 2. INSTALLATION =====
    S.append(Paragraph('2. Installation & Requirements', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Prerequisites', styles['H2']))
    S.extend(B([
        'Odoo 18 Community or Enterprise Edition',
        'Python 3.10+ with <b>requests</b> library',
        'Magento 2.x with REST API enabled',
        'Magento Integration Access Token (Admin > System > Integrations)',
        'Odoo modules: base, product, sale, sale_stock, account, stock',
    ]))
    S.append(Paragraph('Installation Steps', styles['H2']))
    for i, s in enumerate([
        'Copy <b>sdlc_magento_connector</b> folder into your Odoo custom addons directory.',
        'Restart Odoo with <b>-u sdlc_magento_connector</b> or install from Apps menu.',
        'Search for "Magento" in Apps, click <b>Install</b>.',
        'The <b>Magento</b> menu appears in the top navigation bar.',
    ], 1):
        S.append(Paragraph('<b>Step %d:</b> %s' % (i, s), styles['Body']))
    S.append(Paragraph('Magento API Token Setup', styles['H2']))
    for i, s in enumerate([
        'In Magento Admin, go to <b>System > Integrations</b>.',
        'Click <b>Add New Integration</b>.',
        'Enter a name (e.g., "Odoo Connector").',
        'Under <b>API</b> tab, select <b>All</b> resources.',
        'Save and <b>Activate</b> the integration.',
        'Copy the <b>Access Token</b> for use in Odoo.',
    ], 1):
        S.append(Paragraph('%d. %s' % (i, s), styles['Body']))
    S.append(PageBreak())

    # ===== 3. CONFIGURATION =====
    S.append(Paragraph('3. Instance Configuration', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Instances</b> to manage store connections.', styles['Body']))
    S.append(Paragraph('Creating a New Instance', styles['H2']))
    S.append(tbl(['Field', 'Description', 'Example'],
                  [['Instance Name', 'Friendly name for this store', 'EU Magento Store'],
                   ['Base URL', 'Magento store URL', 'https://magento.example.com'],
                   ['Access Token', 'API integration token', 'abc123xyz...'],
                   ['Verify SSL', 'Enable SSL certificate verification', 'Checked'],
                   ['Website ID', 'Magento website ID (usually 1)', '1'],
                   ['Store ID', 'Magento store ID', '1'],
                   ['Store Code', 'Store view code', 'default'],
                   ['Root Category ID', 'Root category for products', '2'],
                   ['Attribute Set Skeleton', 'Template for new attribute sets', '4'],
                   ['Default Payment Method', 'Payment method code', 'checkmo'],
                   ['Default Shipping Method', 'Shipping method code', 'flatrate_flatrate'],
                   ['Default Shipping Amount', 'Shipping cost', '5.00'],
                   ['Customer Default Password', 'For customer creation', 'Change@123'],
                   ], col_widths=[4*cm, 7.5*cm, 5.5*cm]))
    S.append(Spacer(1, 8))
    S.append(Paragraph('Testing the Connection', styles['H2']))
    S.append(Paragraph(
        'Click <b>Test Connection</b> in the form header. A success notification confirms '
        'the API is reachable. If it fails, check the URL and token.', styles['Body']))
    S.append(Paragraph('Sync Buttons', styles['H2']))
    S.append(tbl(['Button', 'Action'],
                  [['Sync Products', 'Pull all products from Magento into Odoo'],
                   ['Sync Categories', 'Pull category tree from Magento'],
                   ['Sync Customers', 'Pull all customers with addresses'],
                   ['Sync Orders', 'Pull orders with invoices, shipments, credit memos'],
                   ['Sync Attribute Sets', 'Pull product attribute set definitions'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(PageBreak())

    # ===== 4. DASHBOARD =====
    S.append(Paragraph('4. Dashboard', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Dashboard</b> for a real-time analytics overview.', styles['Body']))
    S.append(Paragraph('Dashboard Sections', styles['H2']))
    S.append(Paragraph('<b>Header Controls</b>', styles['BodyBold']))
    S.extend(B([
        '<b>Instance Selector</b> - Filter by specific Magento store or view all',
        '<b>Date Range</b> - Last 8 / 14 / 30 / 60 days',
        '<b>Refresh Button</b> - Reload all data',
        '<b>Auto-refresh</b> - Dashboard refreshes every 30 seconds',
    ]))
    S.append(Paragraph('<b>KPI Cards</b>', styles['BodyBold']))
    S.append(tbl(['Card', 'Description', 'Color'],
                  [['Total Amount', 'Sum of order totals + pending amount', 'Orange gradient'],
                   ['Total Orders', 'Order count with change indicator', 'Purple gradient'],
                   ['Delivered Orders', 'Orders marked as delivered', 'Green gradient'],
                   ['Not Delivered', 'Orders pending delivery', 'Pink gradient'],
                   ['Total Customers', 'Synced customer count + change', 'Blue gradient'],
                   ['Total Products', 'Synced product count + change', 'Teal gradient'],
                   ], col_widths=[4*cm, 8*cm, 4*cm]))
    S.append(Paragraph('<b>Charts & Analytics</b>', styles['BodyBold']))
    S.extend(B([
        '<b>Revenue Analytics</b> - Line chart: daily revenue + order count over selected period',
        '<b>Order Status Mix</b> - Stacked progress bars showing status distribution',
        '<b>Top Categories</b> - Donut chart with category revenue breakdown',
        '<b>Top Countries</b> - Horizontal bars showing order distribution by country',
    ]))
    S.append(Paragraph('<b>Sync Health</b>', styles['BodyBold']))
    S.extend(B([
        'Manual Runs / Cron Runs counters',
        'Success Records / Error Records counters',
        'Last sync timestamp, Avg Order Value, Delivered Rate',
    ]))
    S.append(PageBreak())

    # ===== 5. PRODUCTS =====
    S.append(Paragraph('5. Product Management', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Magento Data > Products</b>.', styles['Body']))
    S.append(Paragraph('Product Mapping Model', styles['H2']))
    S.append(Paragraph(
        'Each Magento product has a <b>magento.product.map</b> record that links to both '
        'the Magento product and an Odoo <b>product.product</b> record.', styles['Body']))
    S.append(tbl(['Field', 'Description'],
                  [['Instance', 'Which Magento store'],
                   ['Magento ID', 'Magento product ID (auto-filled on sync)'],
                   ['SKU', 'Product SKU - used for matching'],
                   ['Name', 'Product name'],
                   ['Price', 'Product price'],
                   ['Attribute Set', 'Magento attribute set'],
                   ['Status', 'Enabled / Disabled'],
                   ['Visibility', 'Not Visible / Catalog / Search / Both'],
                   ['Type', 'Simple / Virtual / Downloadable'],
                   ['Weight', 'Product weight'],
                   ['Quantity', 'Stock quantity'],
                   ['Stock Status', 'In Stock / Out of Stock'],
                   ['Categories', 'Linked Magento categories'],
                   ['Description / Short Description', 'Product descriptions'],
                   ['Image', 'Product image (synced from Magento)'],
                   ['Odoo Product', 'Linked Odoo product.product record'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(Paragraph('Product Actions', styles['H2']))
    S.extend(B([
        '<b>Create in Magento</b> - Push new product to Magento (requires SKU)',
        '<b>Update in Magento</b> - Push changes to existing Magento product',
        '<b>Pull from Magento</b> - Refresh data from Magento',
        '<b>Update Mapped Fields</b> - Push only fields configured in field mapping',
        '<b>Refresh Inventory</b> - Sync stock quantities',
    ]))
    S.append(Paragraph(
        '<b>Auto-Sync:</b> When you edit a product mapping and save, changes are automatically '
        'pushed to Magento (unless skip_magento_sync context is set).', styles['Tip']))
    S.append(PageBreak())

    # ===== 6. CUSTOMERS =====
    S.append(Paragraph('6. Customer Management', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Magento Data > Customers</b>.', styles['Body']))
    S.append(tbl(['Field', 'Description'],
                  [['Instance', 'Magento store instance'],
                   ['Magento ID', 'Magento customer ID'],
                   ['Email', 'Required - used for matching'],
                   ['Name Fields', 'Prefix, First, Middle, Last, Suffix'],
                   ['Phone', 'Phone number'],
                   ['Date of Birth', 'Customer birthday'],
                   ['Gender', 'Male / Female / Not Specified'],
                   ['Tax/VAT', 'Tax identification number'],
                   ['Group/Website/Store ID', 'Magento assignment IDs'],
                   ['Address Fields', 'Street, City, Region, Postcode, Country'],
                   ['Default Billing/Shipping', 'Address type flags'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(Paragraph('Customer Actions', styles['H2']))
    S.extend(B([
        '<b>Create in Magento</b> - Creates customer with configured default password',
        '<b>Update in Magento</b> - Updates profile (uses fallback minimal payload if needed)',
        '<b>Pull from Magento</b> - Refresh from Magento API',
        '<b>Auto-Sync:</b> Customers auto-push on create and update',
    ]))
    S.append(Paragraph(
        '<b>Warning:</b> Customer creation requires a default password configured on the instance. '
        'Password must meet Magento\'s minimum length requirement.', styles['Warning']))
    S.append(PageBreak())

    # ===== 7. ORDERS =====
    S.append(Paragraph('7. Order Management', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Sales > Orders</b>.', styles['Body']))
    S.append(Paragraph('Magento Order Model', styles['H2']))
    S.append(tbl(['Field', 'Description'],
                  [['Instance', 'Magento store'],
                   ['Magento ID / Increment ID', 'Magento order identifiers'],
                   ['Status', 'Magento order status (pending, processing, complete, etc.)'],
                   ['Customer', 'Linked Odoo partner'],
                   ['Grand Total / Line Total', 'Order amounts'],
                   ['Currency', 'Order currency code'],
                   ['Order Lines', 'Items with SKU, quantity, price, subtotal'],
                   ['Created At / Updated At', 'Magento timestamps'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(Paragraph('Order Sync Workflow', styles['H2']))
    S.append(Paragraph('<b>Pull from Magento (Sync Orders):</b>', styles['BodyBold']))
    for i, s in enumerate([
        'Fetch all orders from Magento API',
        'For each order: resolve/create customer (res.partner)',
        'Create magento.order + line items',
        'Create linked sale.order in Odoo Sales module',
        'Sync invoices, shipments, and credit memos',
        'Register payments if auto_register_magento_payment is enabled',
    ], 1):
        S.append(Paragraph('%d. %s' % (i, s), styles['Body']))
    S.append(Paragraph('<b>Push to Magento (Create Order):</b>', styles['BodyBold']))
    for i, s in enumerate([
        'Create a guest cart via Magento Cart API',
        'Add items to cart (resolves SKUs)',
        'Set shipping address + shipping method',
        'Set billing address + payment method',
        'Place order - Magento returns order ID',
    ], 1):
        S.append(Paragraph('%d. %s' % (i, s), styles['Body']))
    S.append(PageBreak())

    # ===== 8. INVOICES, SHIPMENTS, CREDIT MEMOS =====
    S.append(Paragraph('8. Invoice, Shipment & Credit Memos', styles['H1']))
    S.append(hr())
    S.append(Paragraph('The connector extends Odoo\'s Sale Order, Stock Picking, and Account Move models.', styles['Body']))
    S.append(Paragraph('Sale Order Enhancements', styles['H2']))
    S.extend(B([
        'Magento tab showing order ID, status, timestamps',
        'Invoice State tracking (Not Invoiced / Partial / Invoiced)',
        'Payment State tracking (Not Paid / Partial / Paid / Refunded)',
        'Total Invoiced / Total Paid monetary fields',
        'Create/Update/Pull buttons for Magento sync',
    ]))
    S.append(Paragraph('Invoice Sync (Account Move)', styles['H2']))
    S.extend(B([
        'When an invoice is <b>posted</b> in Odoo, it auto-creates an invoice in Magento',
        'Magento invoice ID stored on the Odoo invoice',
        'When invoice is <b>paid</b>, Magento order status updated (if configured)',
        'Credit memos synced from Magento with refund amounts',
    ]))
    S.append(Paragraph('Shipment Sync (Stock Picking)', styles['H2']))
    S.extend(B([
        'When delivery is <b>validated</b> (Done), shipment auto-pushes to Magento',
        '<b>Push Shipment to Magento</b> button for manual sync',
        'Magento shipment ID stored on the delivery order',
        'Tracks: ship-to name, customer email, phone, total qty, dates',
    ]))
    S.append(Paragraph('Credit Memo Sync', styles['H2']))
    S.extend(B([
        'Credit memos pulled from Magento during order sync',
        'Tracks: credit memo ID, grand total, tax, subtotal, refund state',
        'Smart button on invoice to view linked credit memos',
    ]))
    S.append(PageBreak())

    # ===== 9. FIELD MAPPING =====
    S.append(Paragraph('9. Field Mapping (Bidirectional)', styles['H1']))
    S.append(hr())
    S.append(Paragraph(
        'Navigate to <b>Magento > Mapping</b> to configure custom field mappings.', styles['Body']))
    S.append(Paragraph('Mapping Types', styles['H2']))
    S.extend(B([
        '<b>Product Mapping</b> - Map product.product / magento.product.map fields to Magento product API fields',
        '<b>Customer Mapping</b> - Map magento.customer fields to Magento customer API fields',
        '<b>Category Mapping</b> - Map magento.category fields to Magento category API fields',
    ]))
    S.append(Paragraph('How Mapping Works', styles['H2']))
    S.append(tbl(['Column', 'Description'],
                  [['Mapping Type', 'Product / Customer / Category'],
                   ['Instance', 'Which Magento store this mapping applies to'],
                   ['Odoo Field', 'Dropdown of all stored fields on the target Odoo model'],
                   ['Magento Field', 'Dropdown of all Magento API fields (auto-fetched from Magento)'],
                   ['Active', 'Enable/disable this individual mapping'],
                   ['Test', 'Validates the mapping and shows a preview report'],
                   ], col_widths=[4*cm, 13*cm]))
    S.append(Paragraph('Loading Available Fields', styles['H2']))
    S.append(Paragraph(
        'Click <b>Load New Fields</b> button to fetch all available fields from your Magento '
        'instance. This queries the Magento API for product attributes, customer attributes, '
        'and category attributes, creating <b>magento.available.field</b> records.', styles['Body']))
    S.append(Paragraph('Advanced Mapping Features', styles['H2']))
    S.extend(B([
        '<b>Nested Fields</b> - Support for dot-notation (e.g., extension_attributes.stock_item.qty)',
        '<b>Custom Attributes</b> - Maps to custom_attributes array (e.g., custom_attributes.color)',
        '<b>Address Fields</b> - Maps to addresses array (e.g., addresses.street)',
        '<b>Type Coercion</b> - Auto-converts between Odoo and Magento field types',
        '<b>Outbound Mapping</b> - Odoo field values injected into Magento API payload on push',
        '<b>Inbound Mapping</b> - Magento API response values set on Odoo fields on pull',
    ]))
    S.append(Paragraph('Testing Mappings', styles['H2']))
    S.append(Paragraph(
        'Click the <b>Test</b> button on any mapping row. This generates a <b>Mapping Report</b> '
        'showing the field-by-field changes and the full API payload. View reports at '
        '<b>Magento > Reports > Mapping Report</b>.', styles['Body']))
    S.append(PageBreak())

    # ===== 10. AUTO SYNC CRON =====
    S.append(Paragraph('10. Auto Sync Cron Jobs', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Configure per-instance on the <b>Instance form > Auto Sync Cron</b> tab.', styles['Body']))
    S.append(Paragraph('Schedule Settings', styles['H2']))
    S.append(tbl(['Field', 'Description'],
                  [['Auto Sync Enabled', 'Master toggle'],
                   ['Frequency', 'Hourly / Daily / Weekly / Monthly'],
                   ['Hour / Minute', 'Time of day to run (server time)'],
                   ['Sync Products', 'Include products in auto sync'],
                   ['Sync Customers', 'Include customers'],
                   ['Sync Categories', 'Include categories'],
                   ['Sync Orders', 'Include orders (with invoices, shipments, credit memos)'],
                   ], col_widths=[4.5*cm, 12.5*cm]))
    S.append(Paragraph(
        'Click <b>Apply Auto-Sync Cron</b> to create/update the scheduled action. '
        'The cron generates a <b>Sync Report</b> for each run.', styles['Body']))
    S.append(Paragraph('Built-in Crons', styles['H2']))
    S.append(tbl(['Cron', 'Interval', 'Action'],
                  [['Magento Product Sync', 'Every 10 minutes', 'Sync products for all instances'],
                   ['Magento Order Sync', 'Every 10 minutes', 'Sync orders for all instances'],
                   ], col_widths=[5*cm, 4*cm, 8*cm]))
    S.append(PageBreak())

    # ===== 11. INVENTORY =====
    S.append(Paragraph('11. Inventory Management', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Inventory</b>.', styles['Body']))
    S.append(Paragraph(
        'The inventory view shows all Magento product mappings with stock data:', styles['Body']))
    S.append(tbl(['Column', 'Description'],
                  [['Product', 'Product name'],
                   ['SKU', 'Product SKU'],
                   ['Quantity', 'Current stock quantity'],
                   ['Stock Status', 'In Stock / Out of Stock'],
                   ['Instance', 'Magento store'],
                   ], col_widths=[4*cm, 13*cm]))
    S.append(Paragraph(
        'Use the <b>Refresh Inventory</b> button on individual products to re-sync stock from Magento.', styles['Body']))
    S.append(PageBreak())

    # ===== 12. SYNC REPORTS =====
    S.append(Paragraph('12. Sync Reports & Logs', styles['H1']))
    S.append(hr())
    S.append(Paragraph('Navigate to <b>Magento > Reports > Sync Reports</b>.', styles['Body']))
    S.append(tbl(['Field', 'Description'],
                  [['Instance', 'Which Magento store'],
                   ['Synced At', 'Timestamp of the sync'],
                   ['Sync Type', 'All / Category / Product / Order / Customer'],
                   ['Mode', 'Manual / Cron'],
                   ['Source Action', 'Button or method that triggered the sync'],
                   ['Total Records', 'Total records processed'],
                   ['Success / Errors', 'Breakdown of results'],
                   ['Categories Created/Updated', 'Category sync details'],
                   ['Products Created/Updated', 'Product sync details'],
                   ['Orders Created/Updated', 'Order sync details'],
                   ['Customers Created/Updated', 'Customer sync details'],
                   ['Inventory Updated', 'Stock updates count'],
                   ['Notes', 'Additional sync details or errors'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(PageBreak())

    # ===== 13. MENU STRUCTURE =====
    S.append(Paragraph('13. Menu Structure', styles['H1']))
    S.append(hr())
    S.append(tbl(['Menu Item', 'Description'],
                  [['Magento', 'Main menu'],
                   ['  Dashboard', 'Real-time analytics with charts and KPIs'],
                   ['  Instances', 'Magento store connections'],
                   ['  Magento Data', 'Parent menu'],
                   ['    Products', 'Magento product mappings'],
                   ['    Customers', 'Magento customers'],
                   ['    Categories', 'Magento categories'],
                   ['  Mapping', 'Parent menu'],
                   ['    Product Mapping', 'Product field mappings'],
                   ['    Customer Mapping', 'Customer field mappings'],
                   ['    Category Mapping', 'Category field mappings'],
                   ['  Sales', 'Parent menu'],
                   ['    Orders', 'All Magento-linked sale orders'],
                   ['    Delivered Orders', 'Completed deliveries'],
                   ['    Not Delivered Orders', 'Pending deliveries'],
                   ['    Invoices', 'Magento-linked invoices'],
                   ['    Shipments', 'Magento-linked shipments'],
                   ['    Credit Memos', 'Magento credit memos'],
                   ['  Inventory', 'Stock status overview'],
                   ['  Reports', 'Parent menu'],
                   ['    Sync Reports', 'Sync audit trail'],
                   ['    Mapping Report', 'Field mapping test results'],
                   ['    Cancelled Orders', 'Cancelled order list'],
                   ], col_widths=[5*cm, 12*cm]))
    S.append(PageBreak())

    # ===== 14. API REFERENCE =====
    S.append(Paragraph('14. Magento API Reference', styles['H1']))
    S.append(hr())
    S.append(Paragraph('The connector uses Magento 2 REST API with Bearer token authentication.', styles['Body']))
    S.append(Paragraph('API Endpoints Used', styles['H2']))
    S.append(tbl(['Endpoint', 'Method', 'Purpose'],
                  [['/rest/V1/products', 'GET', 'List all products'],
                   ['/rest/V1/products/{sku}', 'GET/PUT', 'Get/update product by SKU'],
                   ['/rest/V1/products', 'POST', 'Create new product'],
                   ['/rest/V1/products/{sku}/media', 'POST/PUT', 'Product images'],
                   ['/rest/V1/categories', 'GET/POST', 'List/create categories'],
                   ['/rest/V1/categories/{id}', 'GET/PUT', 'Get/update category'],
                   ['/rest/V1/customers/search', 'GET', 'Search customers'],
                   ['/rest/V1/customers', 'POST', 'Create customer'],
                   ['/rest/V1/customers/{id}', 'GET/PUT', 'Get/update customer'],
                   ['/rest/V1/orders', 'GET', 'List orders'],
                   ['/rest/V1/orders/{id}', 'GET', 'Get order'],
                   ['/rest/V1/order/{id}/invoice', 'POST', 'Create invoice'],
                   ['/rest/V1/order/{id}/ship', 'POST', 'Create shipment'],
                   ['/rest/V1/order/{id}/refund', 'POST', 'Create credit memo'],
                   ['/rest/V1/guest-carts', 'POST', 'Create guest cart'],
                   ['/rest/V1/guest-carts/{id}/items', 'POST', 'Add cart items'],
                   ['/rest/V1/eav/attribute-sets/list', 'GET', 'Attribute sets'],
                   ], col_widths=[6.5*cm, 2.5*cm, 8*cm]))
    S.append(Paragraph('API Fallback Logic', styles['H2']))
    S.append(Paragraph(
        'The connector tries multiple API prefixes in order: '
        '<b>/rest/all/V1</b> then <b>/rest/{store_code}/V1</b> then <b>/rest/V1</b>. '
        'Container-aware fallback (localhost:8080, host.docker.internal) is also supported.', styles['Body']))
    S.append(PageBreak())

    # ===== 15. TROUBLESHOOTING =====
    S.append(Paragraph('15. Troubleshooting', styles['H1']))
    S.append(hr())
    issues = [
        ('Connection test fails', [
            'Verify the Base URL is correct and reachable from the Odoo server',
            'Check the Access Token is valid and not expired',
            'Try with Verify SSL unchecked if using self-signed certificates',
            'Check firewall rules between Odoo and Magento servers',
        ]),
        ('Products not syncing', [
            'Ensure connection is established first',
            'Check Sync Reports for detailed error messages',
            'Verify API token has product resource permissions',
            'Check if products exist in the configured website/store',
        ]),
        ('Orders fail to create in Magento', [
            'Verify Default Payment Method code matches Magento config',
            'Verify Default Shipping Method code matches Magento config',
            'Ensure products have valid SKUs that exist in Magento',
            'Check customer has a valid email and address',
        ]),
        ('Field mapping not applying', [
            'Ensure mappings are Active (toggled on)',
            'Click "Load New Fields" first to fetch Magento fields',
            'Use the Test button to validate each mapping',
            'Check mapping type matches the entity you\'re syncing',
        ]),
        ('Invoice/shipment not syncing to Magento', [
            'Ensure the sale order has a Magento Order ID',
            'Invoice must be Posted before it syncs',
            'Delivery must be Done (validated) before shipment syncs',
            'Check if auto_register_magento_payment is enabled on instance',
        ]),
    ]
    for title, sols in issues:
        S.append(Paragraph('<b>Issue: %s</b>' % title, styles['H3']))
        S.extend(B(sols))
        S.append(Spacer(1, 6))
    S.append(PageBreak())

    # ===== 16. FAQ =====
    S.append(Paragraph('16. FAQ', styles['H1']))
    S.append(hr())
    faqs = [
        ('Can I connect multiple Magento stores?',
         'Yes. Create a separate instance for each store. Products, orders, and customers are isolated per instance.'),
        ('Does the connector support Magento custom attributes?',
         'Yes. The field mapping system supports custom_attributes via dot notation (e.g., custom_attributes.color).'),
        ('How are orders created in Magento from Odoo?',
         'Orders are created via the Magento Guest Cart API. The connector creates a cart, adds items by SKU, '
         'sets addresses and payment/shipping methods, then places the order.'),
        ('What happens when I validate a delivery in Odoo?',
         'The connector automatically creates a shipment in Magento with the corresponding item quantities.'),
        ('What happens when I post an invoice in Odoo?',
         'The connector automatically creates an invoice in Magento for the linked order.'),
        ('Can I sync only specific data types?',
         'Yes. The Auto Sync tab lets you select which entities to sync (Products, Customers, Categories, Orders).'),
        ('How does bidirectional field mapping work?',
         'Outbound: when pushing to Magento, mapped Odoo field values are injected into the API payload. '
         'Inbound: when pulling from Magento, API response values are set on mapped Odoo fields.'),
        ('What is the Mapping Report?',
         'When you click "Test" on a mapping, it runs against a sample record and generates a report showing '
         'what values would change and the full API payload that would be sent.'),
        ('How do I handle credit memos/refunds?',
         'Credit memos are automatically synced from Magento during order sync. They appear as linked '
         'records on the invoice with refund amounts and status.'),
        ('Does the connector auto-sync on save?',
         'Yes. Products, customers, and orders auto-push to Magento when created or updated in Odoo. '
         'Use skip_magento_sync context flag to disable this behavior.'),
    ]
    for q, a in faqs:
        S.append(Paragraph('<b>Q: %s</b>' % q, styles['BodyBold']))
        S.append(Paragraph('A: %s' % a, styles['Body']))
        S.append(Spacer(1, 6))

    # ===== BACK COVER =====
    S.append(PageBreak())
    S.append(Spacer(1, 100))
    S.append(HRFlowable(width='40%', thickness=3, color=PRIMARY, spaceBefore=20, spaceAfter=20))
    S.append(Paragraph('SDLC Magento 2 Connector', ParagraphStyle('x', parent=styles['CoverTitle'], fontSize=20)))
    S.append(Paragraph('User Guide v1.0', styles['CoverSub']))
    S.append(Spacer(1, 20))
    S.append(Paragraph('For support and updates, contact the SDLC Corp team.', styles['CoverSub']))
    S.append(Paragraph('Module: sdlc_magento_connector for Odoo 18', styles['CoverSub']))

    doc.build(S)
    print('PDF generated: %s' % OUTPUT)


if __name__ == '__main__':
    build()
