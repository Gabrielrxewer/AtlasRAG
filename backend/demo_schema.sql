CREATE SCHEMA IF NOT EXISTS demo;

CREATE TABLE IF NOT EXISTS demo.customers (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  email text NOT NULL,
  status text NOT NULL,
  created_at timestamp default now()
);

CREATE TABLE IF NOT EXISTS demo.orders (
  id uuid PRIMARY KEY,
  customer_id uuid REFERENCES demo.customers(id),
  total numeric(10,2) NOT NULL,
  status text NOT NULL,
  created_at timestamp default now()
);

INSERT INTO demo.customers (id, name, email, status)
VALUES
  ('11111111-1111-1111-1111-111111111111', 'Ana Silva', 'ana@example.com', 'ACTIVE'),
  ('22222222-2222-2222-2222-222222222222', 'Bruno Lima', 'bruno@example.com', 'INACTIVE')
ON CONFLICT DO NOTHING;

INSERT INTO demo.orders (id, customer_id, total, status)
VALUES
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', '11111111-1111-1111-1111-111111111111', 120.50, 'PAID'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb', '22222222-2222-2222-2222-222222222222', 60.00, 'CANCELLED')
ON CONFLICT DO NOTHING;
