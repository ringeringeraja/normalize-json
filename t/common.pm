package Common;

sub execute {
  my $binary = shift @_;

  return sub {
    my $string = shift @_;
    my $result = `$binary $string`;
    $result =~ s/^\s+|\s+$//;

    return $result;
  }
}

1;
