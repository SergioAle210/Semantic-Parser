class A {
  let v: integer = 1;
  function constructor() { }
  function inc(): integer { this.v = this.v + 1; return this.v; }
}
class B : A {
  function twice(): integer { return this.v * 2; }
}

function main(): integer {
  let b: B = B();
  let t = b.twice();   // 2
  let u = b.inc();     // 2
  return t + u;        // 4
}
