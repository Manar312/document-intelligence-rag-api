#!/bin/bash
set -eu

mongosh --quiet \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  "$MONGO_DATABASE" \
  --eval "
    db.createUser({
      user: '$MONGO_APP_USERNAME',
      pwd: '$MONGO_APP_PASSWORD',
      roles: [{ role: 'readWrite', db: '$MONGO_DATABASE' }]
    });
    print('Application database user created successfully.');
  "
