-- Products we track (auto parts)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(100) NOT NULL,
    our_price NUMERIC(10,2) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Competitor stores
CREATE TABLE competitors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    base_url VARCHAR(500),
    is_active BOOLEAN DEFAULT TRUE
);

-- Price history (main data table)
CREATE TABLE price_records (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    price NUMERIC(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    in_stock BOOLEAN DEFAULT TRUE,
    scraped_at TIMESTAMPTZ DEFAULT NOW()
);

-- AI-generated reports
CREATE TABLE reports (
    id SERIAL PRIMARY KEY,
    report_type VARCHAR(50) DEFAULT 'daily',
    content TEXT NOT NULL,
    product_count INTEGER,
    generated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Price alerts
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id),
    competitor_id INTEGER NOT NULL REFERENCES competitors(id),
    alert_type VARCHAR(50) NOT NULL,
    old_price NUMERIC(10,2),
    new_price NUMERIC(10,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_price_records_product ON price_records(product_id);
CREATE INDEX idx_price_records_competitor ON price_records(competitor_id);
CREATE INDEX idx_price_records_scraped ON price_records(scraped_at DESC);
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);

-- Seed: Products (auto parts)
INSERT INTO products (name, sku, category, our_price) VALUES
    ('Brake Pads Front (BMW 3 Series)', 'BP-BMW3-F', 'Brakes', 45.90),
    ('Brake Pads Rear (VW Golf)', 'BP-VWG-R', 'Brakes', 38.50),
    ('Oil Filter (Mercedes C-Class)', 'OF-MBC-01', 'Filters', 12.80),
    ('Air Filter (Audi A4)', 'AF-ADA4-01', 'Filters', 18.90),
    ('Spark Plugs Set x4 (Universal)', 'SP-UNI-4X', 'Ignition', 24.60),
    ('Timing Belt Kit (VW 1.9 TDI)', 'TB-VW19-KIT', 'Engine', 89.90),
    ('Wiper Blades Pair (600/475mm)', 'WB-600475', 'Body', 15.40),
    ('Cabin Filter (BMW 5 Series)', 'CF-BMW5-01', 'Filters', 14.20),
    ('Clutch Kit (Opel Astra H)', 'CK-OAH-01', 'Transmission', 142.00),
    ('Shock Absorber Front (Ford Focus)', 'SA-FF-F01', 'Suspension', 67.50);

-- Seed: Competitors
INSERT INTO competitors (name, base_url) VALUES
    ('AutoDoc', 'https://www.autodoc.de'),
    ('KFZteile24', 'https://www.kfzteile24.de'),
    ('ATP Auto', 'https://www.atp-autoteile.de'),
    ('Mister Auto', 'https://www.mister-auto.de');
