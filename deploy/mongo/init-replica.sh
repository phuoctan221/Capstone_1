#!/usr/bin/env bash
# Phase B only. Run INSIDE the mongo1 container:
#   docker compose -f docker-compose.replica.yml exec -T mongo1 bash /scripts/init-replica.sh
# Not used by Phase A (Atlas).
set -euo pipefail

RS_NAME="${MONGO_REPLICA_SET:-rs0}"
DB_NAME="${MONGO_DB_NAME:-capstone1}"
APP_USER="${MONGO_APP_USER:-smartvocab}"
: "${MONGO_APP_PASSWORD:?MONGO_APP_PASSWORD is required}"

until mongosh --host 127.0.0.1:27017 --quiet --eval 'db.runCommand({ ping: 1 }).ok' >/dev/null 2>&1; do
  echo "waiting for mongod on localhost..."
  sleep 2
done

mongosh --host 127.0.0.1:27017 --quiet <<EOF
try {
  rs.status();
  print("replica set already initiated");
} catch (e) {
  rs.initiate({
    _id: "${RS_NAME}",
    members: [
      { _id: 0, host: "mongo1:27017", priority: 2 },
      { _id: 1, host: "mongo2:27017", priority: 1 },
      { _id: 2, host: "mongo3:27017", priority: 1 }
    ]
  });
  print("replica set initiated");
}
EOF

until mongosh --host 127.0.0.1:27017 --quiet --eval 'db.hello().isWritablePrimary' | grep -q true; do
  echo "waiting to become primary..."
  sleep 2
done

mongosh --host 127.0.0.1:27017 --quiet <<EOF
const existing = db.getSiblingDB("admin").getUser("${APP_USER}");
if (existing) {
  print("app user already exists");
} else {
  db.getSiblingDB("admin").createUser({
    user: "${APP_USER}",
    pwd: "${MONGO_APP_PASSWORD}",
    roles: [{ role: "readWrite", db: "${DB_NAME}" }]
  });
  print("app user created");
}
EOF
