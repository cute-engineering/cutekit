rules = {
    "cc": "-c -o $out $in -MD -MF $out.d $flags",
    "cxx": "-c -o $out $in -MD -MF $out.d $flags",
    "as": "-o $out $in $flags",
    "ar": "$flags $out $in",
    "ld": "-o $out $in $flags",
}
