import warnings

# warnings.filterwarnings("ignore", category=YAMLLoadWarning) 


import dask
import numpy as np
import pandas as pd

from q2_sidle._utils import (_setup_dask_client, 
                             _convert_generator_to_delayed_seq_block, 
                             _convert_seq_block_to_dna_fasta_format)
from q2_types.feature_data import (DNAFASTAFormat,
                                   DNAIterator, 
                                   DNASequencesDirectoryFormat
                                   )


def filter_degenerate_sequences(sequences: DNASequencesDirectoryFormat, 
                                max_degen:int=3,
                                chunk_size:int=10000,
                                debug:bool=False, 
                                n_workers:int=1
                                ) -> DNAFASTAFormat:
    """
    Prefilters the database to remove sequences with too many degenerates

    The original SMURF paper recommends filtering sequences with more than 
    3 degenerate nucleotides along their length to limit alignment issues and
    memory.

    Parameters
    ----------
    sequences: q2_types.DNAIterator
        The directory of reference sequences
    max_degen : int, optional
        The maximum number of degenerate nucleotides necessary to retain the
        sequence in the database
    chunk_size: int, optional
        The number of sequences to group for analysis
    debug: bool
        Whether the function should be run in debug mode (without a client)
        or not. `debug` superceeds all options
    n_workers: int, optional
        The number of jobs to initiate. When `n_workers` is 0, the cluster 
        will be able to access all avaliable resources.

    Returns
    -------
    q2_types.DNAFASTAFormat
        The fitlered reads
    # """
    # # Sets up the client
    _setup_dask_client(debug=debug, cluster_config=None,  
                       n_workers=n_workers)
    # Reads in the sequences
    sequences = sequences.view(DNAIterator)
    seq_block = _convert_generator_to_delayed_seq_block(sequences, chunk_size)
    # Performs degenrate filtering
    sub_seq = \
        dask.compute(*_degen_filter(seq_block, max_degen))
    # Converts the sequences back to a file for saving
    ff = _convert_seq_block_to_dna_fasta_format(sub_seq)
    
    return ff



def _degen_filter(sequences, max_degen):
    """
    Prefilters the database to remove sequences with too many degenerates

    Parameters
    ----------
    sequences: SequenceBlocks
        A SequenceBlock object with the reference sequences represented in
        pd.DataFrames where each row is a sequence and each column is a 
        nucleotide position
    max_degen : int, optional
        The maximum number of degenerate nucleotides necessary to retain the
        sequence in the database

    Returns
    -------
    lists of DataFrames
        The filter sequences
    """
    degen_count = [_count_degenerates(seq_) for seq_ in sequences]
    degen_ids = [dask.delayed(lambda x: x.index[x <= max_degen])(count) for 
                 count in degen_count]

    @dask.delayed
    def _filter_seqs(seqs, ids):
        return seqs.loc[seqs.index.isin(ids)]

    sub_seq =[_filter_seqs(seq_, id_) 
              for seq_, id_ in zip(*(sequences, degen_ids))]

    return sub_seq


def _count_degenerates(seq_array):
    """
    Determines the number of degenerate nt in a sequence

    Parameters
    ----------
    seq_array: Dataframe
        A dataframe where each row is a sequence and each column is a basepair
        in that sequence

    Returns
    -------
    Series
        The number of degenerate basepairs in each array

    """
    any_degen = (~seq_array.isin(['A', 'G', 'T', 'C', np.nan]))
    num_deg = any_degen.sum(axis=1)
    
    return num_deg

