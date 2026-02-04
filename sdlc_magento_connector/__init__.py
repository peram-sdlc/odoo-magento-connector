from . import models
from . import services


def pre_init_hook(cr):
    # Drop old FK if present and null-out non-numeric values before switching to Many2one.
    cr.execute("""
        ALTER TABLE magento_product_map
        DROP CONSTRAINT IF EXISTS magento_product_map_attribute_set_id_fkey
    """)
    cr.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'magento_product_map'
                  AND column_name = 'attribute_set_id'
                  AND data_type IN ('character varying', 'text')
            ) THEN
                EXECUTE $sql$
                    UPDATE magento_product_map
                    SET attribute_set_id = NULL
                    WHERE attribute_set_id IS NOT NULL
                      AND attribute_set_id !~ '^[0-9]+$'
                $sql$;
            END IF;
        END $$;
    """)
