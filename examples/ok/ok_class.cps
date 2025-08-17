class A {
  let n: integer;
  function constructor(n: integer) {this.n = n;}
  function get(): integer { return this.n; }
}
let a: A = new A(7);
print(a); 