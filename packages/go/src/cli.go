package main
import (
  "os"
  "encoding/json"
  "normalize/src/normalize"
)

func main() {
  fmapping, err := os.ReadFile(os.Args[1])
  if err != nil {
    panic(err)
  }

  fsample, _ := os.ReadFile(os.Args[2])
  if err != nil {
    panic(err)
  }

  var mapping interface{}
  var sample interface{}

  err = json.Unmarshal([]byte(fmapping), &mapping)
  if err != nil {
    panic(err)
  }

  err = json.Unmarshal([]byte(fsample), &sample)
  if( err != nil ) {
    panic(err)
  }

  normalize.Normalize(sample, mapping)
}
