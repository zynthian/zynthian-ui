# Report missing navigation tests
for x in {B..I}
do
    for y in {2..40}
    do
        [ `grep -c "#Test $x$y" /zynthian/zynthian-ui/test/test_navigation.py` -eq 1 ] || echo $x$y
    done
done
