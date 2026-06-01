import mongoose from 'mongoose';
import dns from 'node:dns';

const uri = process.env.MONGODB_URI;
if (!uri) {
  console.error('MONGODB_URI is required');
  process.exit(2);
}

const dbName = process.env.MONGODB_DB || 'StockAnalysis';

try {
  if (process.env.MONGODB_DNS_SERVERS) {
    dns.setServers(process.env.MONGODB_DNS_SERVERS.split(',').map((item) => item.trim()).filter(Boolean));
  }

  await mongoose.connect(uri, {
    dbName,
    serverSelectionTimeoutMS: 10000,
  });

  const db = mongoose.connection.db;
  const collections = await db.listCollections().toArray();
  const names = collections.map((item) => item.name).sort();
  const knee = db.collection('KneeStocks');
  const total = await knee.countDocuments();
  const kospi = await knee.countDocuments({ market: 'KOSPI' });
  const sp500 = await knee.countDocuments({ market: 'SP500' });
  const latest = await knee
    .find({}, { projection: { _id: 0, market: 1, code: 1, name: 1, updatedAt: 1 } })
    .sort({ updatedAt: -1 })
    .limit(5)
    .toArray();

  console.log(JSON.stringify({
    ok: true,
    dbName,
    collections: names,
    KneeStocks: { total, KOSPI: kospi, SP500: sp500 },
    latest,
  }, null, 2));
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    name: error?.name,
    message: error?.message,
  }, null, 2));
  process.exit(1);
} finally {
  await mongoose.disconnect().catch(() => {});
}
