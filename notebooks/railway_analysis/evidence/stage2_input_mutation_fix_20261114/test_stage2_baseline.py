"""Synthetic contract checks; these are not course-data experiment results."""
import inspect
import unittest
import warnings
import numpy as np
from scipy.spatial.distance import pdist,squareform
from sklearn.manifold import MDS
from stage2_baseline import external_metrics,make_mds,make_model


class BaselineContracts(unittest.TestCase):
    def setUp(self):
        self.points=np.random.default_rng(123).normal(size=(16,2))
        self.distance=squareform(pdist(self.points))

    def test_metrics_ignore_rotation_translation_and_uniform_scale(self):
        rotation=np.array([[0.,-1.],[1.,0.]])
        result=external_metrics(self.distance,7*self.points@rotation+100)
        self.assertLess(result["external_scale_fitted_stress1"],1e-12)
        for key in ("distance_spearman","neighbor_overlap_k5","trustworthiness_k5"):
            self.assertAlmostEqual(result[key],1.)

    def test_metric_mds_uses_precomputed_api(self):
        model,params=make_mds(max_iter=400,n_init=2)
        if "metric_mds" in inspect.signature(MDS).parameters:
            self.assertEqual(params["metric"],"precomputed")
            self.assertTrue(params["metric_mds"])
        else:self.assertEqual(params["dissimilarity"],"precomputed")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coords=model.fit_transform(self.distance)
        self.assertEqual(coords.shape,(16,2))
        self.assertLess(external_metrics(self.distance,coords)["external_scale_fitted_stress1"],.02)

    def test_nonmetric_mds_adapter(self):
        model,params=make_mds(metric=False,max_iter=20,n_init=1)
        self.assertFalse(params.get("metric_mds",params.get("metric")))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coords=model.fit_transform(self.distance)
        self.assertTrue(np.isfinite(coords).all())

    def test_tsne_precomputed_exact_contract(self):
        model,params=make_model("tSNE")
        self.assertEqual(params["metric"],"precomputed")
        self.assertEqual(params["method"],"exact")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coords=model.fit_transform(self.distance)
        self.assertEqual(coords.shape,(16,2))
        self.assertTrue(all(np.isfinite(v) for v in external_metrics(self.distance,coords).values()))

    def test_nonfinite_embedding_is_rejected(self):
        coords=self.points.copy();coords[0,0]=np.nan
        with self.assertRaises(ValueError):external_metrics(self.distance,coords)


if __name__=="__main__":unittest.main(verbosity=2)
