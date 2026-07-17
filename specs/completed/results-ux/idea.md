Future iterations of the collection and number detection will produce a csv that has `time` (ISO 8601)and `race_number` E.g.

```
2026-07-11T14:47:00-07:00,412
2026-07-11T14:51:15-07:00,456
2026-07-11T14:51:17-07:00,422
```


There will also be a CSV that has `race_number`, `name`, `category`.

```
412,"George Watkins","Cat 3",
456,"Matthew Wahl","Cat 3"
422,"Alex Clement", "Cat 4"
```

I need a web based UX to display a "timeline" of crossings.

The timeline should have vertical scroll, with most recent results above. If a gap is more than 3s it should have a space and label with the time, otherwise it should show rider name, number, time of day (`hour:min:sec`) and category.
