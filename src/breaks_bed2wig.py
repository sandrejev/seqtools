import argparse
import pyranges as pr
import pandas as pd
from src.functions import *
from glob import glob
import os
import re


def main(args):
    multiple_breaks_bed_paths = [path for input_glob in args.inputs for path in glob(input_glob)]
    breaks_df = []
    for path in multiple_breaks_bed_paths:
        chr = re.sub(".*(chr[^_]+)_.*", r"\1", os.path.basename(path), flags=re.IGNORECASE).lower()
        breaks_chr = pd.read_csv(path, sep="\t", header=0, names=["Chromosome", "Start", "End", "Feature", "Score", "Strand"]).\
            query("Chromosome == @chr")
        breaks_df.append(breaks_chr)
    breaks_df = pd.concat(breaks_df)

    chromsizes_df = breaks_df.groupby(["Chromosome"], as_index=False).agg({'Start': min, 'End': max})
    bin_chromosomes = {k: [] for k in chromsizes_df.keys()}
    bin_chromosomes["Strand"] = []
    for r, row in chromsizes_df.iterrows():
        numOfChunks = int((row["End"] - row["Start"] - args.window_size) / args.window_step) + 1
        bins = list(range(0, numOfChunks * args.window_step, args.window_step))

        bin_chromosomes["Start"].extend([int(i+row["Start"]) for i in bins*2])
        bin_chromosomes["End"].extend([int(i+args.window_size+row["Start"]) for i in bins*2])
        bin_chromosomes["Strand"].extend(["+"]*len(bins) + ["-"]*len(bins))
        bin_chromosomes["Chromosome"].extend([row["Chromosome"]]*len(bins)*2)
    bin_chromosomes = pr.from_dict(bin_chromosomes)

    coverage_chromosomes = bin_chromosomes.coverage(pr.PyRanges(breaks_df), strandedness="same", overlap_col="Breaks")
    coverage_chromosomes_df = coverage_chromosomes.as_df()
    coverage_chromosomes_df.loc[(coverage_chromosomes_df["Strand"]=="-"), "Breaks"] = -coverage_chromosomes_df.loc[(coverage_chromosomes_df["Strand"]=="-"), "Breaks"]
    coverage_chromosomes = pr.PyRanges(coverage_chromosomes_df)

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path, exist_ok=True)
    coverage_chromosomes[coverage_chromosomes.Strand=="+"].to_bigwig(path=os.path.join(args.output_path, "pos.bw"), chromosome_sizes=pr.PyRanges(chromsizes_df), value_col="Breaks")
    coverage_chromosomes[coverage_chromosomes.Strand=="-"].to_bigwig(path=os.path.join(args.output_path, "neg.bw"), chromosome_sizes=pr.PyRanges(chromsizes_df), value_col="Breaks")

    with open(os.path.join(args.output_path, "custom_tracks.txt"), 'w') as f:
        f.write("#\n# You need to manually replace url to positive and negative strand tracks and \n# add each custom track individually to UCSC genome browser\n#\n")
        f.write("track type=bigWig name=\"{name} (pos)\" description=\"This track represents joins to similar strand\" color=255,0,0, bigDataUrl=pos.bw".format(name=args.track_name) + "\n")
        f.write("track type=bigWig name=\"{name} (neg)\" description=\"This track represents joins to opposite strand\" color=0,255,0, bigDataUrl=neg.bw".format(name=args.track_name) + "\n")

    pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Use a sliding window to aggregate breaks in bed file')
    parser.add_argument('inputs', nargs='+', help='Input .bed files with detected breaks. Can also be multiple files or a whildcard expression (e.g.: path/to/*.bed) ')
    parser.add_argument('chromsizes', help='Chromosome sizes in tab separated format')
    parser.add_argument('output_path', help='Path to folder where all information needed to import to UCSC genome browser will be stored')
    parser.add_argument('--track-name', dest="track_name", help='Name of the UCSC track')
    parser.add_argument('-w|--window-size', dest="window_size", default=int(1e5), type=int, help='Window at which to agregate breaks number')
    parser.add_argument('-s|--window-step', dest="window_step", default=int(1e4), type=int, help='Step after each window')
    args = parser.parse_args()

    if args.track_name is None:
        args.track_name = os.path.basename(args.output_path)

    main(args)