# Smart Loom — Database Files

## For a fresh setup (recommended for your friend)

Run **`smartloom_full_schema.sql`** — it creates everything:

- Database `smartloom`
- All 8 tables with foreign keys
- **8 triggers** (stock, orders, product codes)
- Indexes and views
- Sample demo data

### MySQL Workbench

1. Open `smartloom_full_schema.sql`
2. Execute the full script (⚡ Execute)

### Command line

```bash
mysql -u root -p < database/smartloom_full_schema.sql
```

### Demo logins (after sample data)

| Role     | Email                 | Password |
|----------|------------------------|----------|
| Admin    | admin@smartloom.in     | demo123  |
| Buyer    | buyer@smartloom.in     | demo123  |
| Weaver   | weaver@smartloom.in    | demo123  |
| Supplier | supplier@smartloom.in  | demo123  |

> Passwords are plain text in sample data. After first login, the app re-hashes them automatically.

---

## Already have the database? Add triggers only

```sql
USE smartloom;
```

Then run **`triggers.sql`** (required for the app to work correctly).

---

## Triggers (DBMS requirement)

| Trigger | When | What it does |
|---------|------|----------------|
| `trg_products_after_insert` | After new product | Auto-sets `product_code` (e.g. P-1005) |
| `trg_products_before_update` | Before product edit | Blocks negative stock |
| `trg_materials_before_update` | Before material edit | Blocks negative stock |
| `trg_orders_before_insert` | Before new order | Validates stock, sets `total_price` |
| `trg_orders_after_insert` | After new order | Reduces product stock |
| `trg_orders_after_update` | After order status change | Restores stock if **Cancelled** |
| `trg_material_requests_before_update` | Before delivery | Validates material stock |
| `trg_material_requests_after_update` | After **Delivered** | Reduces material stock |

The Flask app only **inserts/updates** rows; triggers enforce inventory rules in MySQL.

---

## Files in this folder

| File | Purpose |
|------|---------|
| `smartloom_full_schema.sql` | **Complete** DB + tables + triggers + views + sample data |
| `triggers.sql` | Add triggers to an existing database |
| `upgrade_tier1_tier2.sql` | Upgrade an **existing** old database only |

---

## Tables

1. `users` — accounts (Buyer, Weaver, Supplier, Admin)
2. `products` — fabric catalog
3. `materials` — supplier raw materials
4. `orders` — buyer purchases
5. `material_requests` — weaver → supplier requests
6. `notifications` — alerts
7. `activity_log` — audit trail
8. `supplier_ratings` — ratings after delivery

---

## Match `app.py` connection

```python
host="localhost"
user="root"
password="password"   # change if needed
database="smartloom"
```
