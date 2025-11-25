#!/usr/bin/env python
"""调试脚本：检查R1, R2, S1, S2的cluster_index"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'listing_monitor_project.settings')
import django
django.setup()

from example_four_peaks import analyze_four_peaks

clusters, key_levels, current_price = analyze_four_peaks(
    symbol='eth',
    interval='4h',
    price_range_pct=0.15,
    limit=100
)

print('Current price:', current_price)
print()
print('Key levels:')
for name, level in key_levels.items():
    print(f'{name}:')
    print(f'  Price: ${level.price:,.2f}')
    print(f'  Cluster index: {level.cluster_index}')
    print(f'  Boundary type: {level.boundary_type}')
    print(f'  Volume: {level.volume:,.0f} ({level.volume_pct:.1f}%)')
    print(f'  Cluster range: {level.cluster_range}')
    print()

print('=' * 60)
print('Clusters:')
for i, cluster in enumerate(clusters):
    print(f'Cluster {i}: [{cluster.price_low:,.2f}, {cluster.price_high:,.2f}]')
    print(f'  Volume: {cluster.total_volume:,.0f} ({cluster.volume_pct:.1f}%)')
