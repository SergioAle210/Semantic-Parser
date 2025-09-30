function main(): integer {
  try {
    print("en try");
  } catch (e) {
    print("en catch"); // no se ejecuta porque no hay throw/excepciones
  }
  return 0;
}
