let a: integer = 10;
let b = 2;

function foo(): void {
  if (a > b) {
    a = a + b;
  } else {
    a = a - b;
  }
  return;
}

foo();
