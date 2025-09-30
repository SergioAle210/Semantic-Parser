function main(): integer {
  let i: integer = 0;
  let s: integer = 0;
  do {
    s = s + i;
    i = i + 1;
  } while (i < 5);
  return s; // 0+1+2+3+4 = 10
}
