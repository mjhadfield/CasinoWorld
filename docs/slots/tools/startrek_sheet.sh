#!/bin/sh
# Contact sheet of the Star Trek variants: per symbol, the sheet crop then variants 1-3 (cut out).
# usage (from docs/slots/startrek): sh ../tools/startrek_sheet.sh out.png
set -e
out=$1; tmp=$(mktemp -d); i=10
for n in delta enterprise kirk spock worf earth red_planet nebula communicator phaser wild scatter red_delta mug ds9 A K Q J 10; do
  i=$((i+1))
  magick ref/$n.png -resize 220x220 -background '#1a1030' -gravity south -splice 0x26 -fill '#c9c2dd' -pointsize 17 -annotate +0+3 "$n — sheet" $tmp/${i}_0.png
  for v in 1 2 3; do
    magick -size 512x512 xc:'#1a1030' cut/${n}_$v.png -composite -resize 220x220 -background '#1a1030' -gravity south -splice 0x26 -fill '#f3d27a' -pointsize 17 -annotate +0+3 "$n $v" $tmp/${i}_$v.png
  done
done
magick montage $tmp/*.png -tile 8x -geometry +6+6 -background '#0d0818' "$out"
rm -r $tmp
