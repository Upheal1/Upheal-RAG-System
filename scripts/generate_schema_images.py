"""
Generate database schema ER diagram images for documentation.
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# Set style
plt.style.use('default')
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.size'] = 8

# Define colors
COLORS = {
    'auth': '#E3F2FD',      # Light blue
    'clinical': '#E8F5E9',  # Light green
    'roadmap': '#FFF3E0',   # Light orange
    'analytics': '#F3E5F5', # Light purple
    'chat': '#E0F7FA',      # Light cyan
    'system': '#FFFDE7',    # Light yellow
    'pk': '#FFEBEE',        # Light red for PK
    'fk': '#E8EAF6',        # Light indigo for FK
    'header': '#37474F',    # Dark grey
    'border': '#455A64',    # Medium grey
    'arrow': '#78909C',     # Arrow color
}

def draw_table(ax, x, y, width, height, title, columns, color_key, pk_cols=None, fk_cols=None):
    """Draw a database table box."""
    pk_cols = pk_cols or []
    fk_cols = fk_cols or []
    
    # Table header
    header = FancyBboxPatch((x, y + height - 0.4), width, 0.4,
                           boxstyle="round,pad=0.02,rounding_size=0.05",
                           facecolor=COLORS['header'], edgecolor=COLORS['border'],
                           linewidth=1.5, zorder=3)
    ax.add_patch(header)
    ax.text(x + width/2, y + height - 0.2, title, ha='center', va='center',
           fontsize=9, fontweight='bold', color='white', zorder=4)
    
    # Table body
    body = FancyBboxPatch((x, y), width, height - 0.4,
                         boxstyle="round,pad=0.02,rounding_size=0.05",
                         facecolor=COLORS[color_key], edgecolor=COLORS['border'],
                         linewidth=1, zorder=2)
    ax.add_patch(body)
    
    # Columns
    col_y = y + height - 0.6
    for col in columns:
        col_text = col
        col_color = 'black'
        
        if pk_cols and any(pk in col for pk in pk_cols):
            col_text = f"🔑 {col}"
            col_color = '#C62828'
        elif fk_cols and any(fk in col for fk in fk_cols):
            col_text = f"🔗 {col}"
            col_color = '#1565C0'
        
        ax.text(x + 0.05, col_y, col_text, ha='left', va='center',
               fontsize=7, color=col_color, zorder=4)
        col_y -= 0.18
    
    return (x + width/2, y + height, x + width/2, y)  # top_center, bottom_center

def draw_arrow(ax, start, end, style='->', color=None):
    """Draw relationship arrow between tables."""
    color = color or COLORS['arrow']
    ax.annotate('', xy=end, xytext=start,
               arrowprops=dict(arrowstyle=style, color=color, lw=1.5,
                              connectionstyle='arc3,rad=0.1'))

def create_erd():
    """Create Entity-Relationship Diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(18, 14))
    ax.set_xlim(0, 18)
    ax.set_ylim(0, 14)
    ax.axis('off')
    
    # Title
    ax.text(9, 13.5, 'Upheal RAG System - Database Schema (ER Diagram)',
           ha='center', va='center', fontsize=16, fontweight='bold', color=COLORS['header'])
    
    # Auth Layer
    auth_pos = draw_table(ax, 0.5, 11.5, 2.5, 1.5, 'users',
                         ['id (PK)', 'email', 'created_at', 'updated_at'],
                         'auth', pk_cols=['id'])
    
    # Clinical Core - Left
    profile_pos = draw_table(ax, 0.5, 8.5, 2.8, 2.2, 'user_profiles',
                            ['id (PK)', 'user_id (FK)', 'screen_time', 'gad7_score',
                             'phq9_score', 'user_level', 'created_at', 'updated_at'],
                            'clinical', pk_cols=['id'], fk_cols=['user_id'])
    
    interest_pos = draw_table(ax, 0.5, 5.5, 3.0, 2.5, 'interest_profiles',
                             ['id (PK)', 'user_id (FK)', 'tag_preferences',
                              'modality_preferences', 'skipped_modalities',
                              'engagement_quality', 'frustration_score', 'updated_at'],
                             'clinical', pk_cols=['id'], fk_cols=['user_id'])
    
    assess_pos = draw_table(ax, 0.5, 2.5, 2.8, 2.2, 'assessment_responses',
                           ['id (PK)', 'user_id (FK)', 'locale', 'form_payload',
                            'gad7_score', 'phq9_score', 'screen_time', 'recorded_at'],
                           'clinical', pk_cols=['id'], fk_cols=['user_id'])
    
    # Clinical Tasks - Center
    tasks_pos = draw_table(ax, 7.0, 10.0, 3.0, 3.0, 'clinical_tasks',
                          ['id (PK)', 'title', 'description', 'difficulty', 'xp_reward',
                           'safety_risk', 'utility_score', 'clinical_tags', 'modality',
                           'locale', 'chroma_task_id', 'metadata', 'created_at'],
                          'clinical', pk_cols=['id'])
    
    # Roadmap System - Right
    roadmap_pos = draw_table(ax, 13.0, 10.0, 3.2, 2.5, 'roadmaps',
                            ['id (PK)', 'user_id (FK)', 'generation_number',
                             'overall_theme', 'status', 'director_overrides',
                             'generated_at', 'valid_from', 'valid_until'],
                            'roadmap', pk_cols=['id'], fk_cols=['user_id'])
    
    rt_pos = draw_table(ax, 13.0, 7.0, 2.8, 2.2, 'roadmap_tasks',
                       ['id (PK)', 'roadmap_id (FK)', 'task_id (FK)',
                        'sequence_order', 'xp_earned', 'status', 'assigned_at', 'completed_at'],
                       'roadmap', pk_cols=['id'], fk_cols=['roadmap_id', 'task_id'])
    
    mut_pos = draw_table(ax, 13.0, 4.0, 3.0, 2.5, 'roadmap_mutations',
                        ['mutation_id (PK)', 'user_id (FK)', 'directive_id',
                         'kind', 'pre_mutation_state', 'post_mutation_state',
                         'retrieval_overrides', 'rationale', 'triggered_at'],
                        'roadmap', pk_cols=['mutation_id'], fk_cols=['user_id'])
    
    # Analytics - Bottom Center
    il_pos = draw_table(ax, 6.5, 4.0, 2.8, 2.5, 'interaction_logs',
                       ['log_id (PK)', 'user_id (FK)', 'task_id (FK)',
                        'interaction_type', 'completion_time', 'drop_off_point',
                        'xp_earned', 'recorded_at', 'user_rating', 'feedback_text'],
                       'analytics', pk_cols=['log_id'], fk_cols=['user_id', 'task_id'])
    
    rl_pos = draw_table(ax, 6.5, 1.0, 2.8, 2.2, 'retrieval_logs',
                       ['id (PK)', 'user_id (FK)', 'roadmap_id (FK)',
                        'query_embedding', 'retrieved_task_ids', 'similarity_scores',
                        'filters_applied', 'created_at'],
                       'analytics', pk_cols=['id'], fk_cols=['user_id', 'roadmap_id'])
    
    # Chat - Bottom Right
    cs_pos = draw_table(ax, 11.5, 1.0, 2.5, 1.5, 'chat_sessions',
                       ['id (PK)', 'user_id (FK)', 'roadmap_id (FK)', 'created_at'],
                       'chat', pk_cols=['id'], fk_cols=['user_id', 'roadmap_id'])
    
    cm_pos = draw_table(ax, 15.0, 1.0, 2.5, 1.8, 'chat_messages',
                       ['id (PK)', 'session_id (FK)', 'role', 'content', 'metadata', 'created_at'],
                       'chat', pk_cols=['id'], fk_cols=['session_id'])
    
    # System - Bottom Left
    xt_pos = draw_table(ax, 0.5, 0.3, 2.5, 1.5, 'xp_transactions',
                       ['id (PK)', 'user_id (FK)', 'amount', 'source',
                        'reference_id', 'created_at'],
                       'system', pk_cols=['id'], fk_cols=['user_id'])
    
    # Legend
    legend_x, legend_y = 15.5, 13.0
    ax.text(legend_x, legend_y, 'Legend', fontsize=9, fontweight='bold', color=COLORS['header'])
    ax.text(legend_x, legend_y - 0.25, '🔑 Primary Key', fontsize=7, color='#C62828')
    ax.text(legend_x, legend_y - 0.45, '🔗 Foreign Key', fontsize=7, color='#1565C0')
    ax.text(legend_x, legend_y - 0.65, '→ One-to-Many', fontsize=7, color=COLORS['arrow'])
    
    # Draw relationship arrows
    # users -> profiles
    draw_arrow(ax, (auth_pos[0], auth_pos[3]), (profile_pos[0], profile_pos[2]))
    # users -> interest
    draw_arrow(ax, (auth_pos[0], auth_pos[3]), (interest_pos[0], interest_pos[2]))
    # users -> assessment
    draw_arrow(ax, (auth_pos[0] + 0.3, auth_pos[3]), (assess_pos[0] + 0.3, assess_pos[2]))
    # users -> roadmaps
    draw_arrow(ax, (auth_pos[2] + 2.5, auth_pos[3] + 0.3), (roadmap_pos[0] - 0.2, roadmap_pos[2] + 0.5))
    # users -> interaction_logs
    draw_arrow(ax, (auth_pos[0], auth_pos[3]), (il_pos[0] - 0.5, il_pos[2] + 0.5))
    # users -> mutations
    draw_arrow(ax, (auth_pos[2] + 2.5, auth_pos[3] - 0.3), (mut_pos[0] - 0.5, mut_pos[2] + 0.5))
    # users -> xp
    draw_arrow(ax, (auth_pos[0], auth_pos[3]), (xt_pos[0] + 0.5, xt_pos[2] + 0.5))
    
    # roadmaps -> roadmap_tasks
    draw_arrow(ax, (roadmap_pos[0], roadmap_pos[3]), (rt_pos[0], rt_pos[2]))
    # roadmap_tasks -> clinical_tasks
    draw_arrow(ax, (rt_pos[2] + 1.4, rt_pos[3] + 0.5), (tasks_pos[2] + 1.5, tasks_pos[3] + 0.5))
    # interaction_logs -> clinical_tasks
    draw_arrow(ax, (il_pos[2] + 1.4, il_pos[3] + 0.5), (tasks_pos[0] - 0.5, tasks_pos[3] + 0.5))
    
    # roadmaps -> retrieval_logs
    draw_arrow(ax, (roadmap_pos[0] - 0.5, roadmap_pos[3] + 0.5), (rl_pos[2] + 1.4, rl_pos[2] + 0.5))
    # roadmaps -> chat_sessions
    draw_arrow(ax, (roadmap_pos[0], roadmap_pos[3]), (cs_pos[0] - 0.5, cs_pos[2] + 0.3))
    # chat_sessions -> chat_messages
    draw_arrow(ax, (cs_pos[2] + 2.5, cs_pos[3] + 0.3), (cm_pos[0] - 0.2, cm_pos[2] + 0.3))
    
    plt.tight_layout()
    plt.savefig('docs/images/schema-er-diagram.png', dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    plt.close()
    print("✅ ER Diagram saved to docs/images/schema-er-diagram.png")

def create_rag_flow_diagram():
    """Create RAG component flow diagram."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 10))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    
    # Title
    ax.text(7, 9.5, 'RAG Flow - Database Table Mapping',
           ha='center', va='center', fontsize=16, fontweight='bold', color=COLORS['header'])
    
    # RAG Components (top row)
    components = [
        (1.5, 7.5, 'Profiler', COLORS['clinical']),
        (4.5, 7.5, 'Director', COLORS['roadmap']),
        (7.5, 7.5, 'Retriever', COLORS['analytics']),
        (10.5, 7.5, 'Generator', COLORS['chat']),
    ]
    
    for x, y, name, color in components:
        box = FancyBboxPatch((x-0.8, y-0.3), 1.6, 0.6,
                            boxstyle="round,pad=0.02,rounding_size=0.1",
                            facecolor=color, edgecolor=COLORS['border'],
                            linewidth=2, zorder=3)
        ax.add_patch(box)
        ax.text(x, y, name, ha='center', va='center',
               fontsize=11, fontweight='bold', color=COLORS['header'], zorder=4)
    
    # Arrows between components
    for i in range(3):
        ax.annotate('', xy=(components[i+1][0]-0.9, components[i+1][1]),
                   xytext=(components[i][0]+0.9, components[i][1]),
                   arrowprops=dict(arrowstyle='->', color=COLORS['arrow'], lw=2))
    
    # Tables mapped to each component
    table_groups = {
        'Profiler': [
            'assessment_responses',
            'user_profiles',
            'interest_profiles',
        ],
        'Director': [
            'interaction_logs',
            'roadmap_mutations',
            'retrieval_logs',
            'interest_profiles',
        ],
        'Retriever': [
            'clinical_tasks',
            'interest_profiles',
            'retrieval_logs',
        ],
        'Generator': [
            'roadmaps',
            'roadmap_tasks',
            'clinical_tasks',
            'chat_sessions',
            'chat_messages',
        ],
    }
    
    y_positions = {
        'Profiler': 5.5,
        'Director': 5.5,
        'Retriever': 5.5,
        'Generator': 5.5,
    }
    
    for idx, (comp, tables) in enumerate(table_groups.items()):
        x = components[idx][0]
        y_start = y_positions[comp]
        
        # Draw connecting line
        ax.plot([x, x], [7.2, y_start + len(tables)*0.4 + 0.3],
               color=COLORS['arrow'], linewidth=1, linestyle='--', zorder=1)
        
        for i, table in enumerate(tables):
            y = y_start - i*0.5
            box = FancyBboxPatch((x-1.2, y-0.18), 2.4, 0.36,
                                boxstyle="round,pad=0.02,rounding_size=0.05",
                                facecolor='white', edgecolor=COLORS['border'],
                                linewidth=1, zorder=2)
            ax.add_patch(box)
            ax.text(x, y, table, ha='center', va='center',
                   fontsize=8, color=COLORS['header'], zorder=3)
    
    # Telemetry section
    ax.text(7, 2.5, 'Telemetry', ha='center', va='center',
           fontsize=12, fontweight='bold', color=COLORS['header'])
    
    telemetry_tables = ['interaction_logs', 'xp_transactions']
    for i, table in enumerate(telemetry_tables):
        x = 5.5 + i*3
        y = 1.8
        box = FancyBboxPatch((x-1.0, y-0.18), 2.0, 0.36,
                            boxstyle="round,pad=0.02,rounding_size=0.05",
                            facecolor=COLORS['system'], edgecolor=COLORS['border'],
                            linewidth=1, zorder=2)
        ax.add_patch(box)
        ax.text(x, y, table, ha='center', va='center',
               fontsize=9, color=COLORS['header'], zorder=3)
    
    plt.tight_layout()
    plt.savefig('docs/images/schema-rag-flow.png', dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    plt.close()
    print("✅ RAG Flow Diagram saved to docs/images/schema-rag-flow.png")

def create_migration_timeline():
    """Create migration timeline visualization."""
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    
    # Title
    ax.text(7, 7.5, 'Migration Timeline (001 → 011)',
           ha='center', va='center', fontsize=16, fontweight='bold', color=COLORS['header'])
    
    migrations = [
        ('001', 'interaction\n_logs', COLORS['analytics']),
        ('002', 'roadmap\n_mutations', COLORS['roadmap']),
        ('003', 'users &\n_profiles', COLORS['auth']),
        ('004', 'clinical\n_tasks', COLORS['clinical']),
        ('005', 'roadmaps &\n_tasks', COLORS['roadmap']),
        ('006', 'assessment\n_responses', COLORS['clinical']),
        ('007', 'interest\n_profiles', COLORS['clinical']),
        ('008', 'foreign\n_keys', COLORS['system']),
        ('009', 'retrieval_logs\nchat & XP', COLORS['analytics']),
        ('010', 'data\n_retention', COLORS['system']),
        ('011', 'security\n_hardening', COLORS['system']),
    ]
    
    x_start = 1.0
    y_pos = 5.0
    x_step = 1.15
    
    for i, (num, name, color) in enumerate(migrations):
        x = x_start + i * x_step
        
        # Timeline dot
        circle = plt.Circle((x, y_pos + 0.5), 0.15, color=color, ec=COLORS['border'], linewidth=2, zorder=3)
        ax.add_patch(circle)
        ax.text(x, y_pos + 0.5, num, ha='center', va='center',
               fontsize=7, fontweight='bold', color=COLORS['header'], zorder=4)
        
        # Connecting line
        if i < len(migrations) - 1:
            ax.plot([x + 0.15, x + x_step - 0.15], [y_pos + 0.5, y_pos + 0.5],
                   color=COLORS['arrow'], linewidth=2, zorder=1)
        
        # Label box
        box = FancyBboxPatch((x-0.45, y_pos - 1.3), 0.9, 0.9,
                            boxstyle="round,pad=0.02,rounding_size=0.05",
                            facecolor=color, edgecolor=COLORS['border'],
                            linewidth=1, alpha=0.7, zorder=2)
        ax.add_patch(box)
        ax.text(x, y_pos - 0.85, name, ha='center', va='center',
               fontsize=7, color=COLORS['header'], zorder=3)
    
    # Date markers
    ax.text(3.5, 3.0, '2026-05-01', ha='center', va='center',
           fontsize=9, color=COLORS['arrow'], style='italic')
    ax.text(3.5, 2.7, '(001–008)', ha='center', va='center',
           fontsize=8, color=COLORS['arrow'])
    
    ax.text(9.5, 3.0, '2026-05-09', ha='center', va='center',
           fontsize=9, color=COLORS['arrow'], style='italic')
    ax.text(9.5, 2.7, '(009–011)', ha='center', va='center',
           fontsize=8, color=COLORS['arrow'])
    
    # Phase descriptions
    ax.text(3.5, 2.0, 'Core Schema', ha='center', va='center',
           fontsize=9, fontweight='bold', color=COLORS['header'])
    ax.text(9.5, 2.0, 'Enhancement Sprint', ha='center', va='center',
           fontsize=9, fontweight='bold', color=COLORS['header'])
    
    plt.tight_layout()
    plt.savefig('docs/images/schema-migration-timeline.png', dpi=300, bbox_inches='tight',
               facecolor='white', edgecolor='none')
    plt.close()
    print("✅ Migration Timeline saved to docs/images/schema-migration-timeline.png")

if __name__ == '__main__':
    import os
    os.makedirs('docs/images', exist_ok=True)
    
    create_erd()
    create_rag_flow_diagram()
    create_migration_timeline()
    
    print("\n🎉 All schema images generated successfully!")
    print("   - docs/images/schema-er-diagram.png")
    print("   - docs/images/schema-rag-flow.png")
    print("   - docs/images/schema-migration-timeline.png")
