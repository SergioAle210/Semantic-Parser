const PI: integer = 314;

class Animal {
  let nombre: string;
  function constructor(nombre: string) { this.nombre = nombre; }
  function hablar(): string { return this.nombre + " hace ruido."; }
}

class Perro : Animal {
  function constructor(nombre: string) { this.nombre = nombre; }
  function ladrido(): string { return this.nombre + " ladra."; }
}

function outer(x: integer): integer {
  let k: integer = 10;
  function inner(y: integer): integer { return x + y + k; }
  return inner(5);
}

function factorial(n: integer): integer {
  if (n <= 1) { return 1; }
  return n * factorial(n - 1);
}

function main(): integer {
  let x: integer = 5 + 3 * 2 % 3;
  let ok: boolean = !(x < 10 || x > 20);
  let s: string = "Hola " + "Mundo";
  let arr: integer[] = [1, 2, 3];
  let p: Perro = new Perro("Toby");

  print(p.hablar());
  print(p.ladrido());
  print("outer=" + outer(7));
  print("fac=" + factorial(5));

  return 0;
}
