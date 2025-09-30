function main(): integer {
  let xs = [1,2,3,4];
  let acc: integer = 0;
  foreach (x in xs) {
    if ((x % 2) == 0) continue;
    acc = acc + x;
  }
  return acc; // 1 + 3 = 4
}
