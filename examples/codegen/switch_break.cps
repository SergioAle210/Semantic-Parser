function main(): integer {
  let x: integer = 2;
  let r: integer = 0;
  switch (x) {
    case 1:
      r = 10;
      break;
    case 2:
      r = 20;
      // sin break: cae a case 3
    case 3:
      r = r + 3;
      break;
    default:
      r = -1;
  }
  return r; // 23
}
