#!/bin/bash
set -e

# Check for optional SSH key argument
SSH_KEY_PATH=""
if [ -n "$1" ]; then
  SSH_KEY_PATH="$1"
  echo "Using custom SSH key: $SSH_KEY_PATH"
  export GIT_SSH_COMMAND="ssh -i $SSH_KEY_PATH -o StrictHostKeyChecking=no"
fi

# Update the git submodule
echo "Updating songbook-viewer submodule..."
git submodule update --init --remote songbook-viewer

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
