/* 
	Notes:
	[cpnl.created_at] is always equal to [ord.created_at] 
	[cpnl.order_price] is always equal to [ord.price] and [c_ord.order_price]
	An order with a value for reduce_only = false increases/opens a position
	An order with a value for reduce_only = true decreases/closes a position
*/
select
	--pnl.id "Id"
	/* If the trade type was the opposite of the order that closed it */
	 case 
		when cpnl.side = 'Buy' then 'Short'
		when cpnl.side = 'Sell' then 'Long'
		else null
	  end "Trade"
	, ord.created_time "Opened"
	, ord.updated_time "Closed"
	, case 
		when cpnl.closed_pnl > 0 then 'TP ' || cpnl.order_type
		else cpnl.order_type
	  end "Closed By"
	--, cpnl.order_type "Order Type"
	, cpnl.qty "Open Size"
	, cpnl.closed_size "Closed Size"
	, cpnl.avg_entry_price "Avg Entry Price"
	, cpnl.avg_exit_price "Avg Exit Price"
	/* Do not use this field for marker orders, not accurate 
	   because of slippage. Use Average Exit Price */
	-- , cpnl.order_price "Order Price" 
	, cpnl.closed_pnl "P&L"
	, cpnl.fill_count "Fill Count"
	--, cpnl.leverage || 'x' "Leverage"
	--, cpnl.exec_type "Exit Type"
    , right(ord.order_id, 8) "Order Id"
	, ord.side || ' ' || ord.order_type "Closing Order"
	, null "SL Trigger Price"
	--, ord.order_status "Status"
from public."ClosedPnL" cpnl 
inner join public."Orders" ord on cpnl.order_id = ord.order_id
where ord.order_status not in ('Cancelled')

union 

select
	--cpnl.id "Id"
	/* If the trade type was the opposite of the order that closed it */
	  case 
		when cpnl.side = 'Buy' then 'Short'
		when cpnl.side = 'Sell' then 'Long'
		else null
	  end "Trade"
	, cond_ord.created_time "Opened"
	, cond_ord.updated_time "Closed"
	, case 
		when cpnl.closed_pnl > 0 then 'Cond TP ' || cpnl.order_type 
		else 'Cond SL ' || cpnl.order_type
	  end "Closed By"
	--, cpnl.order_type "Order Type"
	, cpnl.qty "Open Size"
	, cpnl.closed_size "Closed Size"
	, cpnl.avg_entry_price "Avg Entry Price"
	, cpnl.avg_exit_price "Avg Exit Price"
	/* Do not use this field for marker orders, not accurate 
	   because of slippage. Use Average Exit Price */
	-- , cpnl.order_price "Order Price" 
	, cpnl.closed_pnl "P&L"
	, cpnl.fill_count "Fill Count"
	--, cpnl.leverage || 'x' "Leverage"
	--, cpnl.exec_type "Exit Type"
    , right(cond_ord.stop_order_id, 8) "Order Id"
	, cond_ord.side || ' ' || cond_ord.order_type "Closing Order"
	, cond_ord.trigger_price "SL Trigger Price"
	--, cond_ord.order_status "Status"

from public."ClosedPnL" cpnl 
inner join public."CondOrders" cond_ord on cpnl.order_id = cond_ord.stop_order_id
where cond_ord.order_status not in ('Cancelled')

order by "Opened" desc