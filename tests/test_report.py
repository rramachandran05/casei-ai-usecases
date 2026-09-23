from casei_geofm.report import compute_metrics, pilot_metrics, review_packet, stratified_sample
from casei_geofm.schemas.candidate import (
    Candidate, CaseiRef, Compatibility, Label, MissionOverlap, Ranking, Satellite, UseCase,
)


def make_fleet():
    cands = []
    for i, (prio, prov, task, phen) in enumerate([
        ("HIGH", "DIRECT_LABEL", "pixel_regression", "vegetation_structure"),
        ("HIGH", "DIRECT_LABEL", "semantic_segmentation", "flood_mapping"),
        ("MEDIUM", "DERIVED_LABEL", "change_detection", "coastal_erosion"),
        ("LOW", "WEAK_OR_PROXY_LABEL", "patch_classification", "soil_chemistry"),
        ("LOW", "MULTIMODAL_PAIR", "contrastive_multimodal_learning", "cloud_microphysics"),
    ]):
        cands.append(Candidate(
            casei=CaseiRef(campaign=f"CAMP{i}", campaign_id=f"c{i}", product_id=f"p{i}"),
            label=Label(target_variable=f"var{i}", label_type="raster_continuous",
                        label_provenance=prov),
            use_case=UseCase(phenomenon=phen, proposed_task=task),
            compatibility=Compatibility(native_or_transformable="TRANSFORMABLE"),
            satellite=Satellite(HLS=MissionOverlap(overlap="YES" if i < 3 else "NO")),
            ranking=Ranking(overall_priority=prio, novelty="HIGH" if i >= 2 else "LOW"),
        ))
    return cands


def test_all_eight_measures_computed():
    m = compute_metrics(make_fleet(), n_products_examined=5, n_products_total=10)
    assert set(m) == {"catalog_coverage", "opportunity_yield", "task_diversity",
                      "label_diversity", "compatibility", "satellite_coincidence",
                      "novel_discovery", "human_agreement"}
    assert m["catalog_coverage"]["pct"] == 50.0
    assert m["satellite_coincidence"]["candidates_with_viable_scenes"] == 3
    # novel = HIGH-novelty phenomena outside the examples list
    assert "coastal_erosion" in m["novel_discovery"]["high_novelty_phenomena_outside_examples"]
    assert "PENDING" in m["human_agreement"]


def test_sample_is_stratified():
    sample = stratified_sample(make_fleet(), per_stratum=1)
    prios = {c.ranking.overall_priority for c in sample}
    provs = {c.label.label_provenance for c in sample}
    tasks = {c.use_case.proposed_task for c in sample}
    assert {"HIGH", "MEDIUM", "LOW"} <= prios
    assert len(provs) >= 3 and len(tasks) >= 3


def test_report_files_render(tmp_path):
    fleet = make_fleet()
    metrics = pilot_metrics(fleet, n_products_examined=5, out_dir=tmp_path)
    packet = review_packet(fleet, out_dir=tmp_path)
    assert metrics.exists() and packet.exists()
    text = metrics.read_text()
    assert "Catalog coverage" in text and "Human agreement" in text
    assert "[ ] Agree" in packet.read_text()
