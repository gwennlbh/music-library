#!/usr/bin/env fish
for track in *.mp3
  set artist (echo $track | cut -d\t -f1)
  set title (echo $track | cut -d\t -f2)
  set vidid (echo $track | cut -d\t -f3 | sed 's/\.mp3$//')
  id3v2 "$track" --artist "$artist" --song "$title" --comment "from youtube video":"$vidid":"EN"
  echo done $artist — $title \($vidid\)
end
