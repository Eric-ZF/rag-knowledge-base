#!/bin/bash
DATE=$(date +%Y%m%d)
VERSION=${1:-$DATE}
echo "Building version: $VERSION"

# Update version in main.jsx
sed -i "s/const BUILD_VERSION = '[^']*'/const BUILD_VERSION = '$VERSION'/" src/main.jsx

# Build
npm run build

# Deploy
cp dist/index.html /var/www/rag/
cp dist/assets/* /var/www/rag/assets/
rm -f /var/www/rag/assets/index-BLaKJEyx.js /var/www/rag/assets/index-DckQaOZl.js 2>/dev/null

echo "Deployed version $VERSION"
