#!/bin/sh

if [ $# -lt 1 ]
then
  echo "Usage: $0 <size>"
  exit 0
fi
if [ $1 -lt 12 ]
then
  echo "Minimum size is 12"
  exit 0
fi

size=$1
mkdir -p $size
pngsize=$(($size - 2))
for file in *.png
do
  convert $file -resize $pngsizex$pngsize $size/$file
done

