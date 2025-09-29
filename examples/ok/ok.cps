function main(): integer {
  let a: integer = 7;
  let b: integer = 3;
  let c: integer = (a + b) * 2;
  print(c);       // 20
  if (c > 10) {
    print("ok");
  } else {
    print(999);
  }
  while (a > 0) {
    a = a - 1;
  }
  return 0;
}
