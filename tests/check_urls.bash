#!/bin/bash


#
# Checks whether URLs still exist
#

URLS="\
    https://raw.githubusercontent.com/geodynamics/axisem/master/MANUAL/manual_axisem1.3.pdf\
    https://github.com/Liang-Ding/seisgen\
    https://instaseis.net\
    "


function check_url {
  if curl --head --silent --fail $1 &> /dev/null; then
    :
  else
    echo "This page does not exist:"
    echo $1
    echo
  fi
}


echo
echo "Checking URLs"
echo

for url in $URLS
do
    echo $url
done
echo

for url in $URLS
do
    check_url $url
done
echo

