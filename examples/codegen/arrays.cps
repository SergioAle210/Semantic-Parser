function main(): integer {
  let a = [10,20,30];
  let s: integer = 0;
  for (let i: integer = 0; i < 3; i = i + 1) {
    s = s + a[i];
  }
  return s;  // 60
}
