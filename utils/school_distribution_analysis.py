import geopandas as gpd
import numpy as np
from scipy.spatial import Voronoi
from shapely.geometry import Point, Polygon

def analyze_school_distribution(input_layer, districts_layer=None):
    """
    Comprehensive school distribution analysis
    
    :param input_layer: Path to schools vector layer
    :param districts_layer: Optional districts layer for more detailed analysis
    :return: Dictionary of analysis results
    """
    # Read input layers
    schools_gdf = gpd.read_file(input_layer)
    
    # Basic spatial statistics
    analysis_results = {
        'basic_metrics': {
            'total_schools': len(schools_gdf),
            'mean_location': {
                'latitude': schools_gdf.geometry.centroid.y.mean(),
                'longitude': schools_gdf.geometry.centroid.x.mean()
            }
        }
    }
    
    # District-level analysis (if districts layer provided)
    if districts_layer:
        districts_gdf = gpd.read_file(districts_layer)
        schools_with_districts = gpd.sjoin(schools_gdf, districts_gdf, how='left')
        
        district_school_counts = schools_with_districts.groupby('district_name').size()
        analysis_results['district_distribution'] = {
            'school_count_by_district': district_school_counts.to_dict(),
            'districts_with_no_schools': list(
                set(districts_gdf['district_name']) - set(district_school_counts.index)
            )
        }
    
    # Spatial Accessibility Analysis
    def calculate_nearest_neighbor_distance(geometry_series):
        """Calculate average nearest neighbor distance"""
        coords = np.array([(p.x, p.y) for p in geometry_series])
        vor = Voronoi(coords)
        
        # Calculate ridge lengths
        ridge_lengths = [
            np.linalg.norm(coords[ridge[0]] - coords[ridge[1]]) 
            for ridge in vor.ridge_points if all(0 <= r < len(coords) for r in ridge)
        ]
        
        return {
            'mean_nearest_neighbor_distance': np.mean(ridge_lengths),
            'min_nearest_neighbor_distance': np.min(ridge_lengths),
            'max_nearest_neighbor_distance': np.max(ridge_lengths)
        }
    
    # Nearest Neighbor Analysis
    analysis_results['spatial_accessibility'] = calculate_nearest_neighbor_distance(
        schools_gdf.geometry
    )
    
    # Coverage Analysis
    def calculate_coverage(schools_geometry, buffer_distance=10):
        """Calculate school coverage area"""
        buffered_schools = schools_geometry.buffer(buffer_distance)
        total_coverage = buffered_schools.unary_union
        
        return {
            'total_coverage_area': total_coverage.area,
            'coverage_percentage': total_coverage.area / schools_geometry.total_bounds.prod() * 100
        }
    
    analysis_results['coverage'] = calculate_coverage(schools_gdf.geometry)
    
    # Spatial Dispersion
    def calculate_spatial_dispersion(geometry_series):
        """Measure of how spread out schools are"""
        centroids = geometry_series.centroid
        centroid_of_centroids = Point(
            centroids.x.mean(), 
            centroids.y.mean()
        )
        
        distances_from_center = [
            centroid.distance(centroid_of_centroids) 
            for centroid in centroids
        ]
        
        return {
            'mean_distance_from_center': np.mean(distances_from_center),
            'std_distance_from_center': np.std(distances_from_center)
        }
    
    analysis_results['spatial_dispersion'] = calculate_spatial_dispersion(
        schools_gdf.geometry
    )
    
    return analysis_results