INTRO_LOOKUP_TYPES = '''\
WITH RECURSIVE typeinfo_tree(
    oid, ns, name, kind, basetype, elemtype, elem_has_bin_input,
    elem_has_bin_output, attrtypoids, attrnames, depth)
AS (
    WITH composite_attrs
    AS (
        SELECT
            c.reltype                                        AS comptype_oid,
            array_agg(ia.atttypid ORDER BY ia.attnum)        AS typoids,
            array_agg(ia.attname::text ORDER BY ia.attnum)   AS names
        FROM
            pg_attribute ia
            INNER JOIN pg_class c
                ON (ia.attrelid = c.oid)
        GROUP BY
            c.reltype
    ),

    typeinfo
    AS (
        SELECT
            t.oid                           AS oid,
            ns.nspname                      AS ns,
            t.typname                       AS name,
            t.typtype                       AS kind,
            (CASE WHEN t.typtype = 'd' THEN
                (WITH RECURSIVE typebases(oid, depth) AS (
                    SELECT
                        t2.typbasetype      AS oid,
                        0                   AS depth
                    FROM
                        pg_type t2
                    WHERE
                        t2.oid = t.oid

                    UNION ALL

                    SELECT
                        t2.typbasetype      AS oid,
                        tb.depth + 1        AS depth
                    FROM
                        pg_type t2,
                        typebases tb
                    WHERE
                       tb.oid = t2.oid
                       AND t2.typbasetype != 0
               ) SELECT oid FROM typebases ORDER BY depth DESC LIMIT 1)

               ELSE NULL
            END)                            AS basetype,
            t.typelem                       AS elemtype,
            elem_t.typreceive::oid != 0     AS elem_has_bin_input,
            elem_t.typsend::oid != 0        AS elem_has_bin_output,
            (CASE WHEN t.typtype = 'c' THEN
                (SELECT ca.typoids
                FROM composite_attrs AS ca
                WHERE ca.comptype_oid = t.oid)

                ELSE NULL
            END)                            AS attrtypoids,
            (CASE WHEN t.typtype = 'c' THEN
                (SELECT ca.names
                FROM composite_attrs AS ca
                WHERE ca.comptype_oid = t.oid)

                ELSE NULL
            END)                            AS attrnames
        FROM
            pg_catalog.pg_type AS t
            INNER JOIN pg_catalog.pg_namespace ns ON (
                ns.oid = t.typnamespace)
            LEFT JOIN pg_type elem_t ON (
                t.typlen = -1 AND
                t.typelem != 0 AND
                t.typelem = elem_t.oid
            )
    )

    SELECT
        ti.oid, ti.ns, ti.name, ti.kind, ti.basetype, ti.elemtype,
        ti.elem_has_bin_input, ti.elem_has_bin_output, ti.attrtypoids,
        ti.attrnames, 0
    FROM
        typeinfo AS ti
    WHERE
        ti.oid = any($1::oid[])

    UNION ALL

    SELECT
        ti.oid, ti.ns, ti.name, ti.kind, ti.basetype, ti.elemtype,
        ti.elem_has_bin_input, ti.elem_has_bin_output, ti.attrtypoids,
        ti.attrnames, tt.depth + 1
    FROM
        typeinfo ti,
        typeinfo_tree tt
    WHERE
        (tt.elemtype IS NOT NULL AND ti.oid = tt.elemtype)
        OR (tt.attrtypoids IS NOT NULL AND ti.oid = any(tt.attrtypoids))
)

SELECT DISTINCT
    *
FROM
    typeinfo_tree
ORDER BY
    depth DESC
'''