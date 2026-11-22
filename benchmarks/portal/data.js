const DATA = Array.from({ length: 40 }, (_, i) => ({
  id: 'R' + String(i + 1).padStart(3, '0'),
  title: 'Record title ' + (i + 1),
  category: ['Software', 'Hardware'][i % 2],
}));
