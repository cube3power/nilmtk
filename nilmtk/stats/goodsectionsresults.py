import pandas as pd
from datetime import timedelta
import matplotlib.pyplot as plt
from ..results import Results
from ..consts import SECS_PER_DAY
from nilmtk.timeframe import TimeFrame, convert_none_to_nat

class GoodSectionsResults(Results):
    """
    Attributes
    ----------
    max_sample_period_td : timedelta
    _data : pd.DataFrame
        index is start date for the whole chunk
        `end` is end date for the whole chunk
        `sections` is a list of nilmtk.TimeFrame objects
    """
    
    name = "good_sections"

    def __init__(self, max_sample_period):
        self.max_sample_period_td = timedelta(seconds=max_sample_period)
        super(GoodSectionsResults, self).__init__()

    def append(self, timeframe, new_results):
        """Append a single result.

        Parameters
        ----------
        timeframe : nilmtk.TimeFrame
        new_results : {'sections': list of TimeFrame objects}
        """
        super(GoodSectionsResults, self).append(timeframe, new_results)

    def combined(self):
        """Merges together any good sections which span multiple segments,
        as long as those segments are adjacent 
        (previous.end - max_sample_period <= next.start <= previous.end).

        Returns
        -------
        sections : list of nilmtk.TimeFrame objects
        """
        sections = []
        end_date_of_prev_row = None
        for index, row in self._data.iterrows():
            row_sections = row['sections']

            # Check if first TimeFrame of row_sections needs to be merged with
            # last TimeFrame of previous section
            if (end_date_of_prev_row is not None and
                end_date_of_prev_row - self.max_sample_period_td <= index <= 
                end_date_of_prev_row and row_sections[0].start is None):

                assert sections[-1].end is None
                sections[-1].end = row_sections[0].end
                row_sections.pop(0)

            # If the previous chunk of code decided that two
            # row_sections[0] and sections[-1] were not in adjacent chunks
            # then check if the are both open-ended and close them...
            if sections and sections[-1].end is None:
                try:
                    sections[-1].end = end_date_of_prev_row
                except ValueError: # end_date_of_prev_row before sections[-1].start
                    pass
            if row_sections and row_sections[0].start is None:
                try:
                    row_sections[0].start = index
                except ValueError:
                    pass
                
            end_date_of_prev_row = row['end']
            sections.extend(row_sections)

        if sections:
            sections[-1].include_end = True
            if sections[-1].end is None:
                sections[-1].end = end_date_of_prev_row

        return sections

    def unify(self, other):
        # TODO!
        warn("Not yet able to do unification of good sections results.")
        super(GoodSectionsResults, self).unify(other)

    def to_dict(self):
        good_sections = self.combined()
        good_sections_list_of_dicts = [timeframe.to_dict() 
                                       for timeframe in good_sections]
        return {'statistics': {'good_sections': good_sections_list_of_dicts}}

    def plot(self, ax=None):
        if ax is None:
            ax = plt.gca()
        ax.xaxis.axis_date()
        for timeframe in self.combined():
            length = ((timeframe.end - timeframe.start).total_seconds() / 
                      SECS_PER_DAY)
            rect = plt.Rectangle((timeframe.start, 0), # bottom left corner
                                 length,
                                 1, # width
                                 color='b') 
            ax.add_patch(rect)            

        ax.autoscale_view()

    def import_from_cache(self, cached_stat, sections):
        # we (deliberately) use duplicate indices to cache GoodSectionResults
        grouped_by_index = cached_stat.groupby(level=0)
        for name, group in grouped_by_index:
            assert group['end'].unique().size == 1
            timeframe = TimeFrame(name, group['end'].iloc[0])
            if timeframe in sections:
                timeframes = [TimeFrame(row['section_start'], row['section_end'])
                              for _, row in group.iterrows()]
                self.append(timeframe, {'sections': [timeframes]})

    def export_to_cache(self):
        """
        Returns
        -------
        DataFrame with three columns: 'end', 'section_end', 'section_start'.
            Instead of storing a list of TimeFrames on each row,
            we store one TimeFrame per row.  This is because pd.HDFStore cannot
            save a DataFrame where one column is a list if using 'table' format'
        """
        index_for_cache = []
        data_for_cache = [] # list of dicts with keys 'end', 'section_end', 'section_start'
        for index, row in self._data.iterrows():
            for section in row['sections']:
                index_for_cache.append(index)
                data_for_cache.append(
                    {'end': row['end'], 
                     'section_start': convert_none_to_nat(section.start),
                     'section_end': convert_none_to_nat(section.end)})
        return pd.DataFrame(data_for_cache, index=index_for_cache)
