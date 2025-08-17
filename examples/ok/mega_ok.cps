const PI: integer = 314;

class Animal {
  let nombre: string;
  function constructor(nombre: string) {
    this.nombre = nombre;
  }
  function hablar(): string {
    return this.nombre + " hace ruido.";
  }
}

class Perro : Animal {
  function constructor(nombre: string) {
    this.nombre = nombre;
  }
  function hablar(): string {
    return this.nombre + " ladra.";
  }
}

function factorial(n: integer): integer {
  if (n <= 1) {
    return 1;
  }
  return n * factorial(n - 1);
}

function main(): integer {
  let x: integer = 5 + 3 * 2;
  let ok: boolean = !(x < 10 || x > 20);
  let s: string = "Hola " + "Mundo";

  let arr: integer[] = [1, 2, 3];
  let matriz: integer[][] = [[1,2], [3,4]];

  print(x);
  print(ok);
  print(s);
  print(arr);

  foreach (n in arr) {
    if (n == 2) {
      continue;
    }
    print(n);
  }

  for (let i: integer = 0; i < 3; i = i + 1) {
    print(i);
  }

  while (x > 0) {
    x = x - 1;
    if (x == 1) {
      break;
    }
  }

  do {
    x = x + 1;
  } while (x < 2);

  switch (x) {
    case 0:
      print("cero");
    case 2:
      print("dos");
    default:
      print("otro");
  }

  try {
    let peligro = arr[100];
  } catch (err) {
    print(err);
  }

  let p: Perro = new Perro("Toby");
  print(p.hablar());

  let idxVal: integer = arr[0];
  let mval: integer = matriz[1][0];

  return factorial(5);
}
