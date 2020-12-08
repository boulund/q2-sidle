from unittest import TestCase, main

import os
import shutil
import warnings


import numpy as np
import numpy.testing as npt
import pandas as pd
import pandas.testing as pdt
import skbio
from skbio import DNA

from qiime2 import Artifact, Metadata
from qiime2.plugins.sidle import methods as sidle
from q2_sidle.plugin_setup import plugin

import q2_sidle.tests.test_set as ts


class PluginSetupTest(TestCase):
    def setUp(self):
        self.base_dir = \
            os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                         'files/little_test')
        self.ref_seqs = \
            Artifact.load(os.path.join(self.base_dir, 'full_db.qza'))
        self.region1_db_seqs = \
            Artifact.load(os.path.join(self.base_dir, 'region1_db_seqs.qza'))
        self.region2_db_seqs = \
            Artifact.load(os.path.join(self.base_dir, 'region2_db_seqs.qza'))
        self.region1_db_map = ts.region1_db_map
        self.region2_db_map = ts.region2_db_map
        self.rep_seqs1 = \
            Artifact.load(os.path.join(self.base_dir, 'region1_rep_set.qza'))
        self.align1 = ts.region1_align
        self.align2 = ts.region2_align
        self.kmer_map1 = ts.region1_db_map
        self.kmer_map2 = ts.region2_db_map
        self.table1 = ts.region1_counts
        self.table2 = ts.region2_counts
        self.seq_map = ts.seq_map
        self.taxonomy = ts.taxonomy
        self.count1 = ts.region1_counts
    
    def test_plugin_setup(self):
        self.assertEqual(plugin.name, 'sidle')

    def test_filter_degenerate_sequences(self):
        known = self.ref_seqs.view(pd.Series).copy().astype(str).drop(['seq3'])

        test = sidle.filter_degenerate_sequences(
            self.ref_seqs, 
            max_degen=0, 
            debug=True
            )
        test = test.filtered_sequences.view(pd.Series).astype(str)
        pdt.assert_series_equal(known, test)

    def test_prepare_extracted_region(self):
        test_seqs, test_map = \
            sidle.prepare_extracted_region(self.region2_db_seqs,
                                           region='Gotham',
                                           trim_length=15,
                                           fwd_primer='CACCTCGTN',
                                           rev_primer='CACGTCAK',
                                           debug=True,
                                           )
        pdt.assert_series_equal(
            test_seqs.view(pd.Series).astype(str),
            self.region2_db_seqs.view(pd.Series).astype(str)
            )
        pdt.assert_frame_equal(test_map.view(pd.DataFrame), 
                               self.region2_db_map.view(pd.DataFrame))

    def test_trim_dada2_posthoc(self):
        test_table, test_seqs = \
            sidle.trim_dada2_posthoc(self.count1,
                                     self.rep_seqs1,
                                     hashed_feature_ids=False,
                                     )

        known_seqs = self.rep_seqs1.view(pd.Series).astype(str).copy()
        known_seqs.index = known_seqs
        known_table = self.count1.view(pd.DataFrame).copy()
        known_table.columns = known_seqs.index

        pdt.assert_frame_equal(test_table.view(pd.DataFrame), known_table)
        pdt.assert_series_equal(test_seqs.view(pd.Series).astype(str), 
                                known_seqs)

    def test_align_regional_kmers(self):
        warnings.filterwarnings('ignore', 
                                category=skbio.io.FormatIdentificationWarning)
        test_align = \
            sidle.align_regional_kmers(self.region1_db_seqs,
                                       self.rep_seqs1,
                                       region='Bludhaven',
                                       max_mismatch=2,
                                       debug=True,
                                       ).regional_alignment
        # self.assertEqual(len(test_discard.view(pd.Series)), 0)
        pdt.assert_frame_equal(
            self.align1.view(pd.DataFrame),
            test_align.view(pd.DataFrame).sort_values(['kmer', 'asv'])
            )

    def test_reconstruct_counts(self):

        known_summary = pd.DataFrame.from_dict(orient='index', data={
            'seq1': {'num-regions': 2, 
                     'total-kmers-mapped': 2, 
                     'mean-kmer-per-region': 1.,
                     'stdv-kmer-per-region': 0.,
                     'mapped-asvs': 'asv01|asv06'
                    },
            'seq2': {'num-regions': 2, 
                     'total-kmers-mapped': 2, 
                     'mean-kmer-per-region': 1,
                     'stdv-kmer-per-region': 0,
                     'mapped-asvs': 'asv01|asv07',
                    },
            'seq3': {'num-regions': 2, 
                     'total-kmers-mapped': 3, 
                     'mean-kmer-per-region': 1.5,
                     'stdv-kmer-per-region': np.std([1, 2], ddof=1),
                     'mapped-asvs': 'asv02|asv03|asv08'
                    },
            'seq4': {'num-regions': 1, 
                     'total-kmers-mapped': 1, 
                     'mean-kmer-per-region': 1,
                     'stdv-kmer-per-region': 0,
                     'mapped-asvs': 'asv09'
                    },
            'seq5': {'num-regions': 2, 
                     'total-kmers-mapped': 2, 
                     'mean-kmer-per-region': 1,
                     'stdv-kmer-per-region': 0,
                     'mapped-asvs': 'asv04|asv05|asv10',
                    },
            'seq6': {'num-regions': 2, 
                     'total-kmers-mapped': 2, 
                     'mean-kmer-per-region': 1,
                     'stdv-kmer-per-region': 0,
                     'mapped-asvs': 'asv04|asv05|asv11',
                    },
            })
        known_summary.index.set_names('feature-id', inplace=True)        
        count_table, summary, mapping = \
            sidle.reconstruct_counts(
                region=['Bludhaven', 'Gotham'],
                kmer_map=[self.kmer_map1, self.kmer_map2],
                regional_alignment=[self.align1, self.align2],
                regional_table=[self.table1, self.table2],
                debug=True,
                min_abund=1e-2,
                min_counts=10)
        pdt.assert_frame_equal(
            count_table.view(pd.DataFrame),
            pd.DataFrame( 
                data=np.array([[100.,  50,   0,  50,  50, 50],
                               [100.,  25, 100,  25,  25, 25],
                               [  0., 100, 100,   0,  50, 50]]),
                index=pd.Index(['sample1', 'sample2', 'sample3']),
                columns=['seq1', 'seq2', 'seq3', 'seq4', 'seq5', 'seq6']
            )
        )
        pdt.assert_frame_equal(self.seq_map.view(pd.DataFrame), 
                               mapping.view(pd.DataFrame))
        pdt.assert_frame_equal(known_summary, summary.view(pd.DataFrame))

    def test_reconstruct_taxonomy(self):
        test = sidle.reconstruct_taxonomy(self.seq_map, 
                                          self.taxonomy,
                                          database='greengenes',
                                          define_missing='ignore'
                                          ).reconstructed_taxonomy
        pdt.assert_series_equal(self.taxonomy.view(pd.Series),
                                test.view(pd.Series))

    def test_reconstruct_fragment_rep_seqs(self):
        recon_map = Artifact.import_data(
            'FeatureData[SidleReconstruction]', 
            pd.DataFrame(data=[['seq01|seq02'], 
                               ['seq01|seq02'], 
                               ['seq03|seq04'], 
                               ['seq03|seq04'], 
                               ['seq05']],
                      index=pd.Index(['seq01', 'seq02', 'seq03', 'seq04', 
                                      'seq05'], name='db-seq'),
                      columns=['clean_name'])
            )
        recon_summary = Artifact.import_data(
            'FeatureData[ReconstructionSummary]',
            Metadata(pd.DataFrame(data=[[1, 2, 2, 0, 'asv01|asv02'],
                                        [2, 3, 1.5, np.std([1, 2], ddof=1), 
                                         'asv03|asv04'],
                                        [2, 2, 1, 0, 'asv07|asv08']],
                                 index=pd.Index(['seq01|seq02', 'seq03|seq04', 
                                                 'seq05'], name='feature-id'),
                                columns=['num-regions', 'total-kmers-mapped', 
                                         'mean-kmer-per-region', 
                                         'stdv-kmer-per-region', 
                                         'mapped-asvs']))
        )
        aligned_seqs = Artifact.import_data(
            'FeatureData[AlignedSequence]', 
            skbio.TabularMSA([
                DNA('CTAGTCATGCGAAGCGGCTCAGGATGATGATGAAGAC-------------------'
                    '--------------', metadata={'id': 'seq01'}),
                DNA('CTAGTCATGCGAAGCGGCTCAGGATGATGATGAAGAC-------------------'
                    '--------------', metadata={'id': 'seq02'}),
                DNA('CATAGTCATWTCCGCGTTGGAGTTATGATGATGAWACCACCTCGTCCCAGTTCCGC'
                    'GCTTCTGACGTGC-', metadata={'id': 'seq03'}),
                DNA('------------------GGAGTTATGATGA--AGACCACCTCGTCCCAGTTCCGC'
                    'GCTTCTGACGTGCC', metadata={'id': 'seq04'}),
                DNA('CATAGTCATCGTTTATGTATGCCCATGATGATGCGAGCACCTCGTATGGATGTAGA'
                    'GCCACTGACGTGCG', metadata={'id': 'seq05'}),
            ])
        )
        known = pd.Series(
            data=['GCGAAGCGGCTCAGG',
                  'WTCCGCGTTGGAGTTATGATGATGAGACCACCTCGTCCCAGTTCCGCGCTTC'],
            index=pd.Index(['seq01|seq02', 'seq03|seq04']),
            )
        test = sidle.reconstruct_fragment_rep_seqs(
            region=['Bludhaven', 'Gotham'],
            kmer_map=[Artifact.load(os.path.join(self.base_dir, 
                                    'frag_r1_db_map.qza')),
                      Artifact.load(os.path.join(self.base_dir, 
                                    'frag_r2_db_map.qza'))],
            reconstruction_map=recon_map, 
            reconstruction_summary=recon_summary, 
            aligned_sequences=aligned_seqs,
            ).representative_fragments
        pdt.assert_series_equal(known, test.view(pd.Series).astype(str))

    def test_integration(self):
        # This will run through a slightly more complex dataset...
        base_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), 
                         'files/integration')
        test_dir = os.path.join(base_dir, 'test')
        known_dir = os.path.join(base_dir, 'known')
        data_dir = os.path.join(base_dir, 'data')
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

        ### Sequence extraction
        region1_seqs, region1_map = sidle.prepare_extracted_region(
            Artifact.load(os.path.join(data_dir, 'region1-extract-seqs.qza')),
            fwd_primer='TGGCGGACGGGTGAGTAA',
            rev_primer='CTGCTGCCTCCCGTAGGA',
            trim_length=50,
            region='1',
            debug=True,
            )
        known = \
            Artifact.load(os.path.join(known_dir, 'region1-kmer-seqs.qza'))
        pdt.assert_series_equal(region1_seqs.view(pd.Series).astype(str),
                                known.view(pd.Series).astype(str))
        known = \
            Artifact.load(os.path.join(known_dir, 'region1-kmer-map.qza'))
        pdt.assert_frame_equal(known.view(pd.DataFrame).sort_index(), 
                              region1_map.view(pd.DataFrame).sort_index())

        region2_seqs, region2_map = sidle.prepare_extracted_region(
            Artifact.load(os.path.join(data_dir, 'region2-extract-seqs.qza')),
            fwd_primer='CAGCAGCCGCGGTAATAC',
            rev_primer='CGCATTTCACCGCTACAC',
            trim_length=50,
            region='2',
            debug=True,
            )
        known = \
            Artifact.load(os.path.join(known_dir, 'region2-kmer-seqs.qza'))
        pdt.assert_series_equal(region2_seqs.view(pd.Series).astype(str),
                                known.view(pd.Series).astype(str))
        known = \
            Artifact.load(os.path.join(known_dir, 'region2-kmer-map.qza'))
        pdt.assert_frame_equal(known.view(pd.DataFrame), 
                              region2_map.view(pd.DataFrame))
        region3_seqs, region3_map = sidle.prepare_extracted_region(
            Artifact.load(os.path.join(data_dir, 'region3-extract-seqs.qza')),
            fwd_primer='GCACAAGCGGTGGAGCAT',
            rev_primer='CGCTCGTTGCGGGACTTA',
            trim_length=50,
            region='3',
            debug=True,
            )
        known = \
            Artifact.load(os.path.join(known_dir, 'region3-kmer-seqs.qza'))
        pdt.assert_series_equal(region3_seqs.view(pd.Series).astype(str),
                                known.view(pd.Series).astype(str))
        known = \
            Artifact.load(os.path.join(known_dir, 'region3-kmer-map.qza'))
        pdt.assert_frame_equal(known.view(pd.DataFrame), 
                              region3_map.view(pd.DataFrame))

        
        ### Regiomal Alignment
        align1 = sidle.align_regional_kmers(
            region1_seqs, 
            Artifact.load(os.path.join(data_dir, 'region1-rep-seq.qza')),
            region='1',
            max_mismatch=2,
            debug=True,
            chunk_size=1,
            ).regional_alignment
        known = \
            Artifact.load(os.path.join(known_dir, 'region1-align-map.qza'))
        pdt.assert_frame_equal(align1.view(pd.DataFrame).sort_values(['kmer', 'asv']),
                               known.view(pd.DataFrame))

        align2 = sidle.align_regional_kmers(
            region2_seqs, 
            Artifact.load(os.path.join(data_dir, 'region2-rep-seq.qza')),
            region='2',
            max_mismatch=2,
            debug=True,
            ).regional_alignment
        known = \
            Artifact.load(os.path.join(known_dir, 'region2-align-map.qza'))
        pdt.assert_frame_equal(align2.view(pd.DataFrame).sort_values(['kmer', 'asv']),
                               known.view(pd.DataFrame))
        
        align3 = sidle.align_regional_kmers(
            region3_seqs, 
            Artifact.load(os.path.join(data_dir, 'region3-rep-seq.qza')),
            region='3',
            max_mismatch=2,
             debug=True,
            ).regional_alignment
        known = \
            Artifact.load(os.path.join(known_dir, 'region3-align-map.qza'))
        pdt.assert_frame_equal(align3.view(pd.DataFrame).sort_values(['kmer', 'asv']),
                               known.view(pd.DataFrame))

        count1 = Artifact.load(os.path.join(data_dir, 'region1-counts.qza'))
        count2 = Artifact.load(os.path.join(data_dir, 'region2-counts.qza'))
        count3 = Artifact.load(os.path.join(data_dir, 'region3-counts.qza'))

        ### Reconstruction
        table, summary, map_ = sidle.reconstruct_counts(
            region=['1', '2', '3'],
            kmer_map=[region1_map, region2_map, region3_map],
            regional_alignment=[align1, align2, align3],
            regional_table=[count1, count2, count3],
            debug=True,
            min_counts=100,
            min_abund=1e-5,
            count_degenerates=False,
        )
        known = \
            Artifact.load(os.path.join(known_dir, 'reconstructed-table.qza'))
        pdt.assert_frame_equal(known.view(pd.DataFrame), 
                               table.view(pd.DataFrame))
        known = \
            Artifact.load(os.path.join(known_dir, 'reconstructed-summary.qza'))
        # ASV mapping was optional in the  original sidle. This is  tested
        # elsewhere  and dealing w ith it is going to suck. 
        pdt.assert_frame_equal(
            known.view(pd.DataFrame),
            summary.view(pd.DataFrame).drop(columns=['mapped-asvs'])
            )
        known = \
            Artifact.load(os.path.join(known_dir, 'sidle-reconstruction.qza'))
        pdt.assert_series_equal(known.view(pd.Series), map_.view(pd.Series))



if __name__ == '__main__':
    main()