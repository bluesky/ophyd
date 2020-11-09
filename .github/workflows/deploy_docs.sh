#!/usr/bin/env bash

# Set env variable 'BUILD_DIR' to point to the directory that contains documentation
#   e.g BUILD_DIR="docs/build/html"
# GITHUB_TOKEN should be also set (e.g. GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }})

echo "====================================================================="
echo "SCRIPT: PUBLISHING DOCUMENTATION TO GITHUB PAGES"
set -eu

REPO_URI="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
REMOTE_NAME="origin"
TARGET_BRANCH="gh-pages"

# Get the repository name: if repository is 'bluesky/some-repo', the name is 'some-repo'
REPO_NAME=$(echo $GITHUB_REPOSITORY | awk -F '/' '{print $2}')
echo "====================================================================="
echo "GitHub repository: ${GITHUB_REPOSITORY}"
echo "Repository name: ${REPO_NAME}"

CACHE_DIR="/tmp/repo_cache"
echo "====================================================================="
echo "Creating temporary directory: ${CACHE_DIR}"
mkdir $CACHE_DIR
cd $CACHE_DIR

echo "====================================================================="
echo "Cloning GitHub repository: ${GITHUB_REPOSITORY}"
git clone "https://github.com/${GITHUB_REPOSITORY}.git"
cd $REPO_NAME

echo "====================================================================="
echo "Checking out the target branch: ${TARGET_BRANCH}"
git checkout $TARGET_BRANCH

echo "====================================================================="
echo "Setting up Git user name and email ... (${GITHUB_ACTOR})"
git config user.name "$GITHUB_ACTOR"
git config user.email "${GITHUB_ACTOR}@bots.github.com"

# Remove all files and directories except hidden directories.
#   -f - exits with 0 if there is not files to delete
echo "====================================================================="
echo "Removing the all files ('${TARGET_BRANCH}' branch) ..."
rm -rf !\(.*\)

echo "====================================================================="
echo "Copying files from build directory: ${BUILD_DIR}"
# Copy everything including hidden files
cp -r "${GITHUB_WORKSPACE}/${BUILD_DIR}"/. .
ls -al

echo "====================================================================="
echo "Difference:"
git diff

echo "====================================================================="
echo "Adding changes ..."
git add .

echo "====================================================================="
echo "Committing changes ..."
git diff-index --quiet HEAD || git commit -am "Deployed Docs"
echo "Changes were committed."

echo "====================================================================="
echo "Pushing changes to the repository ..."
git remote set-url "$REMOTE_NAME" "$REPO_URI"  # includes access token
# Allow 'push' to fail in case of collision with another build
git push "$REMOTE_NAME" "$TARGET_BRANCH"
echo "Documents were published to '${TARGET_BRANCH}' branch."
