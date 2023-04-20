BEGIN {
  push @INC, 't';
}

our $BINARY = @ARGV[0] or die('please provide the binary');

use common;
use Test::More;

my $e = Common::execute($BINARY);

ok(
  $e->("samples/mapping1.json samples/sample1.json | jq -r '.entry.items[1].title'")
  eq 'Product name #2',
  'normal translation'
);

ok(
  $e->("samples/mapping1-reverse.json samples/sample1-reverse.json | jq -r '.shipment.products[1].name'")
  eq 'Product name #2',
  'reverse translation'
);

ok(
  $e->("samples/mapping2.json samples/sample2.json | jq '.age'")
  eq '50',
  'default value'
);

ok(
  $e->("samples/mapping3.json samples/sample3.json | jq '.entry.products[1].stock'")
  eq '5',
  'integer casting'
);

done_testing();
