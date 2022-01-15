-- View: public.v_Trades

-- DROP VIEW public."v_Trades";

CREATE OR REPLACE VIEW public."v_Trades"
 AS
 SELECT
        CASE
            WHEN cpnl.side::text = 'Buy'::text THEN 'Short'::text
            WHEN cpnl.side::text = 'Sell'::text THEN 'Long'::text
            ELSE NULL::text
        END AS "Trade",
    ord.created_time AS "Opened",
    ord.updated_time AS "Closed",
    cpnl.qty AS "Open Size",
    cpnl.closed_size AS "Closed Size",
    cpnl.avg_entry_price AS "Avg Entry Price",
    cpnl.avg_exit_price AS "Avg Exit Price",
    cpnl.closed_pnl AS "P&L",
    cpnl.fill_count AS "Fill Count",
    "right"(ord.order_id::text, 8) AS "Order Id",
        CASE
            WHEN cpnl.closed_pnl > 0::double precision THEN ('TP '::text || cpnl.order_type::text)::character varying
            ELSE cpnl.order_type
        END AS "Closed By",
    (ord.side::text || ' '::text) "Closing Order",
    NULL::double precision AS "SL Trigger Price"
   FROM "ClosedPnL" cpnl
     JOIN "Orders" ord ON cpnl.order_id::text = ord.order_id::text
  WHERE ord.order_status::text <> 'Cancelled'::text
UNION
 SELECT
        CASE
            WHEN cpnl.side::text = 'Buy'::text THEN 'Short'::text
            WHEN cpnl.side::text = 'Sell'::text THEN 'Long'::text
            ELSE NULL::text
        END AS "Trade",
    cond_ord.created_time AS "Opened",
    cond_ord.updated_time AS "Closed",
    cpnl.qty AS "Open Size",
    cpnl.closed_size AS "Closed Size",
    cpnl.avg_entry_price AS "Avg Entry Price",
    cpnl.avg_exit_price AS "Avg Exit Price",
    cpnl.closed_pnl AS "P&L",
    cpnl.fill_count AS "Fill Count",
    "right"(cond_ord.stop_order_id::text, 8) AS "Order Id",
        CASE
            WHEN cpnl.closed_pnl > 0::double precision THEN 'Cond TP '::text || cpnl.order_type::text
            ELSE 'Cond SL '::text || cpnl.order_type::text
        END AS "Closed By",
    (cond_ord.side::text || ' '::text) AS "Closing Order",
    cond_ord.trigger_price AS "SL Trigger Price"
   FROM "ClosedPnL" cpnl
     JOIN "CondOrders" cond_ord ON cpnl.order_id::text = cond_ord.stop_order_id::text
  WHERE cond_ord.order_status::text <> 'Cancelled'::text
  ORDER BY 2 DESC;

ALTER TABLE public."v_Trades"
    OWNER TO "CryptoMakerUser";
GRANT SELECT ON public."v_Trades" TO "CryptoMakerUser";	


