#!/bin/bash


#
# Checks whether web pages still exist
#

URLS="\
    https://raw.githubusercontent.com/geodynamics/axisem/master/MANUAL/manual_axisem1.3.pdf\
    https://github.com/Liang-Ding/seisgen\
    https://instaseis.net\
    https://docs.obspy.org/packages/autogen/obspy.core.stream.Stream.html
    https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.html
    https://docs.xarray.dev/en/stable/generated/xarray.DataArray.html
    https://docs.obspy.org/packages/autogen/obspy.imaging.mopad_wrapper.beach.html#supported-basis-systems
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

# for broken link, stop immediately
set -e

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
echo SUCCESS
echo

