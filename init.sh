#!/usr/bin/bash

sudo apt-get install git -y
git clone https://github.com/oermenz/midihub.git
cd midihub

echo "This will take a while, grab a cup of coffee..."
echo
./setup.sh
echo
echo "All done!"
echo
