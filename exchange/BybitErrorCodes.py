BybitErrorCodes = {
    "10001": "Params Error",
    "10002": "Request not authorized - an API key is required and should be included in all requests.",
    "10003": "Too many requests - please use WebSocket for live updates. Current limit is %s requests per minute.",
    "10004": "invalid sign",
    "10005": "permission denied for current apikey",
    "10006": "System not responding. Request status unknown. Please contact live support.",
    "10007": "Response timeout from backend server. Delivery and request status unknown.",
    "10010": "request ip mismatch",
    "10016": "Service not available.",
    "10017": "request path not found or request method is invalid",
    "10018": "exceed ip rate limit",
    "33004": "apikey already expired",
    "35014": "over order limit",
    "130001": "Not get position",
    "130002": "wallet is nil",
    "130003": "the pz status is not normal",
    "130004": "Order number is out of permissible range",
    "130005": "Order price is out of permissible range",
    "130006": "order qty is out of permissible range",
    "130007": "Order price is out of permissible range",
    "130008": "order_type invalid",
    "130009": "The number of contracts below min limit allowed",
    "130010": "order not exists or Too late to operate",
    "130011": "Operation not allowed as position is undergoing liquidation",
    "130012": "Operation not allowed as position is undergoing ADL",
    "130013": "stop_order trail value invalid",
    "130014": "stop_order trigger price invalid",
    "130015": "stop_order expected_direction or base_price invalid",
    "130016": "invalid stop_order_type, cannot replace price",
    "130017": "invalid stop_order_type, cannot replace qty",
    "130018": "invalid trail_value",
    "130019": "invalid stop_order_type, cannot replace trigger_price",
    "130020": "invalid stop_order_type, cannot replace trail_value",
    "130021": "order cost not available",
    "130024": "cannot set tp_sl_ts for zero position",
    "130025": "below < 10% of base price",
    "130026": "the price is too high",
    "130027": "the price set for Buy position should be higher than base_price",
    "130028": "the price set for Sell position should be between base_price and liq_price",
    "130029": "the price set for Buy position should be between liq_price and base_price",
    "130030": "the price set for Sell position should be lower than base_price",
    "130032": "invalid order_status, cannot cancel or execute trigger",
    "130033": "number of stop order >= 10",
    "130034": "stop_order cannot replace",
    "130035": "Too freq to cancel, Try it later",
    "130037": "Order already cancelled",
    "130040": "position will be liq",
    "130041": "AvailableBalanceE8 less than 0",
    "130049": "available balance not enough",
    "130050": "Any adjustments made will trigger liq",
    "130051": "cannot set leverage, due to risk limit",
    "130052": "cannot set leverage, below the lower limit",
    "130056": "the position is in cross_margin",
    "130057": "the position size is 0",
    "130058": "can not set margin less than minPositionCost",
    "130059": "can not set pz open limit more than symbol limit",
    "130060": "autoAddMargin not changed",
    "130061": "not change fee, invalid req",
    "130062": "can not set pz open limit less than current buy pz value",
    "130063": "can not set pz open limit less than current sell pz value",
    "130064": "just support usdt",
    "130074": "expect Rising, trigger_price <= current",
    "130075": "expect Falling, trigger_price >= current",
    "130076": "replace params invalid",
    "130077": "the deposit req has handled",
    "130078": "the withdraw req has handled",
    "130079": "the rotate req has handled",
    "130101": "unknown request for create order",
    "130102": "unknown request for cancel order",
    "130103": "unknown request for cancelAll",
    "130104": "unknown request for LiqExecuteReq, req param not match liqExecuteReq",
    "130105": "unknown request for pre create order",
    "130106": "unknown req for query order",
    "130107": "unmatch request for triggeredToActiveImpl",
    "130108": "unknown request for addMargin",
    "130109": "unknown request for calculatePositionPnl",
    "130110": "unknown request for qryAssetImpl",
    "130111": "unknown request for query_position_list",
    "130112": "unknown request for setAutoAddMargin",
    "130113": "unknown request for setFeeRate",
    "130114": "unknown request for setLeverage",
    "130115": "unknown request for setMargin",
    "130116": "unknown request for setOpenLimit",
    "130117": "unknown request for setTpSlTs",
    "130118": "unknown request for settleFundingFeeReq",
    "130119": "unknown request for setPositionMode",
    "130120": "unknown request for walletDeposit",
    "130121": "unknown request for walletWithDraw",
    "130122": "unknown request for rotateRealisedPnl",
    "130123": "unknown request for AdlExecute",
    "130124": "unknown request for AdlCleanReq",
    "130125": "No change made for TP/SL price",
    "130126": "No orders",
    "130023": "Will be triggered Liq after order is completed",
    "130127": "Take Profit, Stop Loss and Trailing Stop Loss are not modified",
    "130145": "Close order side is large than position's leaving qty",
    "130149": "Order creation successful but SL/TP setting failed",
    "130150": "Please try again later.",
    "130151": "Switching failed. Please cancel the current SL/TP setting",
    "130152": "Switching failed. Please cancel the current SL/TP setting",
    "130153": "Switching failed. Please cancel the current SL/TP setting",
    "130154": "Switching failed. Please cancel the SL/TP setting of active orders",
    "130155": "Insufficient quantity required to set TP/SL",
    "130156": "Replacing active order price and qty simultaneously is not allowed",
    "130157": "Amendment failed. SL/TP price cannot be amended as order is partially filled",
    "130158": "SL/TP price cannot be amended under 'Full' position mode",
    "130159": "Max SL/TP orders under 'Partial' mode is 20",
    "134026": "Risk limit has not been changed.",
    "132011": "Current position size exceeds risk limit. Risk limit adjustment failed.",
    "130090": "Risk limit is invalid."
}