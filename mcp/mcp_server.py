import os
import httpx
from dotenv import load_dotenv
from fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

load_dotenv()

BASE_URL = os.getenv("DJANGO_BASE_URL", "http://localhost:8000")
MCP_API_KEY = os.getenv("MCP_API_KEY", "")

mcp = FastMCP("fci-stash-mcp")


# ---------------------------------------------------------------------------
# API key middleware
# ---------------------------------------------------------------------------

class APIKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # SSE negotiation happens on GET /sse — still require the key
        key = request.headers.get("X-MCP-Key", "")
        if key != MCP_API_KEY:
            return Response("Unauthorized", status_code=401)
        return await call_next(request)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get(path: str, params: dict | None = None) -> dict | list:
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        return r.json()


async def _patch(path: str, body: dict) -> dict:
    url = f"{BASE_URL}{path}"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.patch(url, json=body)
        r.raise_for_status()
        return r.json()


def _product_name(sale: dict) -> str:
    p = sale.get("product") or {}
    if isinstance(p, dict):
        return p.get("name", "—")
    return str(p)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_order_by_email(email: str) -> dict:
    """
    Find all orders placed by a customer email address.

    Returns order id, product name, sale_price, shipping_status,
    sale_date, and customer_name for every matching order.
    """
    # Fetch all shipping-info records and find those matching the email
    shipping_data = await _get("/api/sales/shipping-info/")
    if isinstance(shipping_data, dict):
        shipping_records = shipping_data.get("results", shipping_data.get("data", []))
    else:
        shipping_records = shipping_data

    matched_sale_ids = {
        rec["sale"] if isinstance(rec.get("sale"), int) else rec.get("sale", {}).get("id")
        for rec in shipping_records
        if rec.get("customer_email", "").lower() == email.lower()
    }

    if not matched_sale_ids:
        return {"orders": [], "message": f"No orders found for email: {email}"}

    # Build customer_name lookup from shipping records
    email_info: dict[int, dict] = {}
    for rec in shipping_records:
        sid = rec["sale"] if isinstance(rec.get("sale"), int) else rec.get("sale", {}).get("id")
        if sid in matched_sale_ids:
            email_info[sid] = rec

    # Fetch full sale details for each matched order
    orders = []
    for sale_id in matched_sale_ids:
        try:
            sale = await _get(f"/api/sales/{sale_id}/")
            info = email_info.get(sale_id, {})
            orders.append({
                "order_id": sale.get("id"),
                "product_name": _product_name(sale),
                "sale_price": sale.get("sale_price"),
                "shipping_status": sale.get("shipping_status"),
                "sale_date": sale.get("sale_date"),
                "customer_name": info.get("customer_name", sale.get("customer", "—")),
                "customer_email": info.get("customer_email", email),
            })
        except httpx.HTTPStatusError:
            continue

    return {"orders": orders, "total": len(orders)}


@mcp.tool()
async def get_order_status(order_id: int) -> dict:
    """
    Get the full status of a single order including shipping details.

    Returns order id, product name, shipping_status, sale_date,
    customer_name, and any available shipping/tracking info.
    """
    try:
        sale = await _get(f"/api/sales/{order_id}/")
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"Order {order_id} not found"}
        raise

    result = {
        "order_id": sale.get("id"),
        "product_name": _product_name(sale),
        "sale_price": sale.get("sale_price"),
        "quantity_sold": sale.get("quantity_sold"),
        "shipping_status": sale.get("shipping_status"),
        "sale_date": sale.get("sale_date"),
        "customer": sale.get("customer"),
        "is_refunded": sale.get("is_refunded"),
        "refunded_at": sale.get("refunded_at"),
        "shipping_info": None,
    }

    # Attempt to fetch shipping info (may 404 if not set)
    try:
        shipping = await _get(f"/api/sales/shipping-info/{order_id}/get_shipping_info/")
        result["shipping_info"] = {
            "customer_name": shipping.get("customer_name"),
            "customer_email": shipping.get("customer_email"),
            "customer_phone": shipping.get("customer_phone"),
            "customer_address": shipping.get("customer_address"),
            "customer_pincode": shipping.get("customer_pincode"),
        }
    except httpx.HTTPStatusError:
        result["shipping_info"] = None

    return result


@mcp.tool()
async def get_unshipped_orders() -> dict:
    """
    Return all orders that have not yet been shipped.

    For each order returns: order_id, product_name, customer_name,
    customer_email, sale_date, and current shipping_status.
    """
    data = await _get("/api/sales/unshipped/")

    raw_sales = data.get("unshipped_sales", data) if isinstance(data, dict) else data

    # Fetch shipping info to enrich with customer email
    shipping_data = await _get("/api/sales/shipping-info/")
    if isinstance(shipping_data, dict):
        shipping_records = shipping_data.get("results", shipping_data.get("data", []))
    else:
        shipping_records = shipping_data

    email_map: dict[int, str] = {}
    name_map: dict[int, str] = {}
    for rec in shipping_records:
        sid = rec["sale"] if isinstance(rec.get("sale"), int) else rec.get("sale", {}).get("id")
        if sid:
            email_map[sid] = rec.get("customer_email", "")
            name_map[sid] = rec.get("customer_name", "")

    orders = []
    for sale in raw_sales:
        sid = sale.get("id")
        orders.append({
            "order_id": sid,
            "product_name": _product_name(sale),
            "shipping_status": sale.get("shipping_status"),
            "sale_date": sale.get("sale_date"),
            "customer": sale.get("customer"),
            "customer_name": name_map.get(sid, sale.get("customer", "—")),
            "customer_email": email_map.get(sid, "—"),
        })

    total_unshipped = data.get("total_unshipped_items") if isinstance(data, dict) else len(orders)

    return {
        "orders": orders,
        "count": len(orders),
        "total_unshipped_items": total_unshipped,
    }


VALID_STATUSES = {"SHIPPING_PENDING", "SHIPPING_PLACED", "SHIPPED"}


@mcp.tool()
async def update_shipping_status(order_id: int, status: str) -> dict:
    """
    Update the shipping status of an order.

    Valid values for status: SHIPPING_PENDING, SHIPPING_PLACED, SHIPPED.
    Returns a confirmation and the new status.
    """
    status = status.upper().strip()
    if status not in VALID_STATUSES:
        return {
            "error": f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        }

    try:
        result = await _patch(
            f"/api/sales/{order_id}/update_shipping_status/",
            {"shipping_status": status},
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return {"error": f"Order {order_id} not found"}
        raise

    return {
        "success": True,
        "order_id": order_id,
        "new_shipping_status": result.get("shipping_status", status),
        "message": f"Order {order_id} shipping status updated to {status}",
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = mcp.sse_app()
    app.add_middleware(APIKeyMiddleware)

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
