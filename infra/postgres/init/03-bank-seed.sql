-- Synthetic demo data. Dates are relative to now() so "yesterday" stays yesterday.
SET ROLE bank_api;
SET search_path = bank;

INSERT INTO customers (id, full_name, phone, preferred_language) VALUES
  ('CUST-1001', 'Aarav Sharma', '+919800000001', 'en'),
  ('CUST-1002', 'Priya Nair',   '+919800000002', 'hi'),
  ('CUST-1003', 'Rohan Mehta',  '+919800000003', 'en');

INSERT INTO accounts (id, customer_id, account_type, balance_paise, masked_number) VALUES
  ('ACC-2001', 'CUST-1001', 'savings', 8245000, 'XXXX4821'),   -- ₹82,450.00 (the demo balance)
  ('ACC-2002', 'CUST-1002', 'savings', 15632050, 'XXXX7310'),  -- ₹1,56,320.50
  ('ACC-2003', 'CUST-1003', 'current', 412575, 'XXXX0094');    -- ₹4,125.75

INSERT INTO cards (id, customer_id, account_id, card_type, network, last4) VALUES
  ('CARD-3001', 'CUST-1001', 'ACC-2001', 'debit',  'Visa',       '4821'),
  ('CARD-3002', 'CUST-1001', NULL,       'credit', 'Visa',       '9934'),
  ('CARD-3003', 'CUST-1002', 'ACC-2002', 'debit',  'RuPay',      '7310'),
  ('CARD-3004', 'CUST-1003', 'ACC-2003', 'debit',  'Mastercard', '0094');

INSERT INTO transactions (id, account_id, card_id, posted_at, amount_paise, merchant, category, channel, description) VALUES
  -- CUST-1001: the ₹1,999 "what is this?" charge is yesterday's annual renewal.
  ('TXN-5001', 'ACC-2001', 'CARD-3001', now() - interval '1 day' - interval '3 hours', -199900, 'StreamPlus', 'subscription', 'autodebit', 'StreamPlus Premium annual renewal'),
  ('TXN-5002', 'ACC-2001', NULL,        now() - interval '1 day' - interval '9 hours', -45000,  'Swiggy',     'food',         'upi',       'UPI payment to Swiggy'),
  ('TXN-5003', 'ACC-2001', 'CARD-3001', now() - interval '2 days',                     -324950, 'Croma',      'electronics',  'card',      'POS purchase, Croma Andheri'),
  ('TXN-5004', 'ACC-2001', NULL,        now() - interval '4 days',                     -1200000,'Landlord',   'rent',         'netbanking','Rent transfer, September'),
  ('TXN-5005', 'ACC-2001', NULL,        now() - interval '6 days',                     8500000, 'Acme Corp',  'salary',       'transfer',  'Salary credit'),
  ('TXN-5006', 'ACC-2001', 'CARD-3001', now() - interval '7 days',                     -200000, 'HDFC ATM',   'cash',         'atm',       'ATM withdrawal, Bandra'),
  -- CUST-1002
  ('TXN-5101', 'ACC-2002', 'CARD-3003', now() - interval '1 day',                      -89900,  'BigBasket',  'groceries',    'card',      'Online purchase, BigBasket'),
  ('TXN-5102', 'ACC-2002', NULL,        now() - interval '3 days',                     -150000, 'Electricity Board', 'utilities', 'autodebit', 'Electricity bill autopay'),
  -- CUST-1003
  ('TXN-5201', 'ACC-2003', 'CARD-3004', now() - interval '1 day',                      -199900, 'FitLife Gym','fitness',      'card',      'Monthly membership');

RESET ROLE;
