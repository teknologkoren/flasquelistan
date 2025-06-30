#!/bin/bash
set -e

# Navigate to the submodule directory
cd songbook-viewer

# Install dependencies and build the project
npm install
npm run build

# Navigate back to the root
cd ..

# Create the target directory if it doesn't exist
mkdir -p flasquelistan/songbook_dist

# Copy the built files to the new distribution directory
cp -r songbook-viewer/dist/* flasquelistan/songbook_dist/

echo "Songbook build complete. Files copied to flasquelistan/songbook_dist"
