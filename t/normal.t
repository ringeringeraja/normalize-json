BEGIN {
  push @INC, 't';
}

our $BINARY = @ARGV[0] or die('please provide the binary');

use common;
use Test::More;

my $e = Common::execute($BINARY);

ok(
  $e->("samples/mapping1.json samples/sample1.json | jq -r '.entry.items[1].title'")
  eq 'Product name #2'
);


done_testing();
