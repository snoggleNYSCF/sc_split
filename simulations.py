"""
Simulate SNV/Barcode Matrices (ref/alt) for genotype-free demultiplexing on pooled scRNA-seq Jon Xu Lachlan Coin Aug 2018 jun.xu@uq.edu.au """

import sys
import vcf  # https://pyvcf.readthedocs.io/en/latest/INTRO.html
import math
import numpy as np
import pysam as ps  # http://pysam.readthedocs.io/en/latest/api.html#sam-bam-files
import pandas as pd
from random import randint
import datetime

class SNV_data:
    """
    Stores data on each SNV
    """

    def __init__(self, chrom, pos, ref, alt, samples):

        self.CHROM = chrom   # chromosome number
        self.POS = pos       # position on chromosome
        self.REF = ref       # reference base
        self.ALT = alt       # alternate base
        self.SAMPLES = samples   # mixed samples


def simulate_base_calls_matrix(file_i, file_o, all_SNVs, barcodes):
    """
    Build pandas DataFrame
    Parameters:
        file_s(str): Path to sam file (0-based positions)
        all_SNVs: list of SNV_data objects
        barcodes(list): cell barcodes
    """

    num = len(all_SNVs[0].SAMPLES)

    # randomly put all barcodes into the groups
    groups = [randint(0, num-1) for item in range(len(barcodes))]

    all_POS = []   # snv positions (1-based positions from vcf file)
    for entry in all_SNVs:
        pos = str(entry.CHROM) + ':' + str(entry.POS)
        if pos not in all_POS:
            all_POS.append(pos)

    in_sam = ps.AlignmentFile(file_i, 'rb')
    out_sam = ps.AlignmentFile(file_o, 'wb', template=in_sam)

    ref_base_calls_mtx = pd.DataFrame(np.zeros((len(all_POS), len(barcodes))), index=all_POS, columns=barcodes)
    alt_base_calls_mtx = pd.DataFrame(np.zeros((len(all_POS), len(barcodes))), index=all_POS, columns=barcodes)
    print('Num Pos:', len(all_POS), ', Num barcodes:', len(barcodes))

    for snv in all_SNVs:
        position = str(snv.CHROM) + ':' + str(snv.POS)
        # use pysam.AlignedSegment.fetch instead of pysam.AlignedSegment.pileup which doesn't contain barcode information
        for read in in_sam.fetch(snv.CHROM, snv.POS-1, snv.POS+1):
            if read.flag < 256:   # only valid reads
                if (snv.POS - 1) in read.get_reference_positions():
                    # if the read aligned positions cover the SNV position
                    try:
                        barcode = read.get_tag('CB')
                        sample = groups[barcodes.index(barcode)]
                        if np.argmax(snv.SAMPLES[sample]['GL']) == 0:
                            ref_base_calls_mtx.loc[position, barcode] += 1
                            new = snv.REF
                        elif np.argmax(snv.SAMPLES[sample]['GL']) == 2:
                            alt_base_calls_mtx.loc[position, barcode] += 1
                            new = snv.ALT
                        else:
                            coin = randint(0,1)
                            if coin == 0:
                                ref_base_calls_mtx.loc[position, barcode] += 1
                                new = snv.REF
                            else:
                                alt_base_calls_mtx.loc[position, barcode] += 1
                                new = snv.ALT

                        # update the base in bam file
                        read.query_sequence[[item for item in read.get_aligned_pairs(True) if item[1] == (snv.POS - 1)][0][0]] = new
                        out_sam.write(read)

                    except:
                        pass

    ref_base_calls_mtx.index.name = alt_base_calls_mtx.index.name = 'SNV'

    return (ref_base_calls_mtx, alt_base_calls_mtx)


def main():

    # Input and output files
    file_v = 'sim.vcf'
    file_i = 'input.bam'
    file_o = 'sim.bam'
    file_bc = 'sim.tsv'
    out_csv_ref = 'ref_sim.csv'
    out_csv_alt = 'alt_sim.csv'
    
    all_SNVs = []  # list of SNV_data objects
    for record in vcf.Reader(open(file_v, 'r')):
        # only keep SNVs with heterozygous genotypes, and ignore SNV with multiple bases (e.g. GGGT/GGAT)
        if (len(record.REF) == 1) & (len(record.ALT) == 1):
            all_SNVs.append(SNV_data(record.CHROM, record.POS, record.REF, record.ALT, record.samples))
    
    barcodes = []   # list of cell barcodes
    for line in open(file_bc, 'r'):
        barcodes.append(line.strip())

    base_calls_mtx = simulate_base_calls_matrix(file_i, file_o, all_SNVs, barcodes)
    base_calls_mtx[0].to_csv('{}'.format(out_csv_ref))
    base_calls_mtx[1].to_csv('{}'.format(out_csv_alt))

if __name__ == "__main__":
    main()
