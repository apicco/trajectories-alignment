from trajalign.traj import Traj
from trajalign.average import load_directory
from trajalign.average import MSD
from trajalign.average import nanMAD 
from scipy.interpolate import UnivariateSpline #need to install py35-scikit-learn
import numpy as np
import copy as cp

from matplotlib import pyplot as plt


def align( path_target , path_reference , ch1 , ch2 ):
	"""
	align( path_target , path_reference , ch1 , ch2 , ):
	aligns in space and in time the trajectories identified by path_target to path_reference,
	which is the reference trajectory. As a convention within the align function trajectories 
	labeled with 1 are the target trajectories that need to be ligned to the reference 
	trajectories, which are labelled with 2.The alignment uses the trajectories in ch1 
	and ch2, which have been acquired simultaneously and whose alignment has been 
	corrected for chormatic aberrations and imaging misalignments. 'ch1' refers to 
	the trajectories that need to be aligned to the average trajectory in 'path_target'. 
	'ch2' refers to 'path_reference'.
	"""

	def spline( t1 , t2 ) :

		"""
		interpolate t1 or t2 with a spline.
		"""

		#the interpolation function
		def interpolation( to_interpolate , delta_t ) :
			
			interpolated_traj = Traj( interpolated = 'True' )
			interpolated_traj.annotations( to_interpolate.annotations() )
			interpolated_traj.annotations()[ 'delta_t' ] = delta_t
	
			#the new time intervals for the trajectory interpolated
			t = [ to_interpolate.start() ]
			while( t[ len(t) - 1 ] <= to_interpolate.end() ) :
				t.append( t[ len(t) - 1 ] + delta_t )
			
			interpolated_traj.input_values( 
					name = 't' , 
					x = t ,
					unit = to_interpolate.annotations( 't_unit' ) 
					)
	
			for attribute in to_interpolate.attributes() : 	
				
				if attribute in [ 'f' , 'mol' ] :
	
					s = UnivariateSpline( to_interpolate.t() , getattr( to_interpolate , '_'+attribute ) )
					interpolated_traj.input_values( 
							name = attribute , 
							x = s( interpolated_traj.t() )
							)
	
				if attribute == 'coord' :
	
					s_x = UnivariateSpline( to_interpolate.t() , to_interpolate.coord()[ 0 ] )
					s_y = UnivariateSpline( to_interpolate.t() , to_interpolate.coord()[ 1 ] )
					interpolated_traj.input_values( 
							name = 'coord' , 
							x = [ s_x( interpolated_traj.t() ) , s_y( interpolated_traj.t() ) ],
							)

			return( interpolated_traj )
	
		#the trajectory with the largest delta_t will be the one that will 
		#be splined. 

		if t1.annotations()[ 'delta_t' ] >= t2.annotations()[ 'delta_t' ] :

			delta_t = float(t2.annotations()[ 'delta_t' ])
		
		else :
			
			delta_t = float(t1.annotations()[ 'delta_t' ])

		not_nan = [ i for i in range( len( t1 ) ) if t1.f( i ) == t1.f( i ) ]
		t1_to_interpolate = t1.extract( not_nan )

		not_nan = [ i for i in range( len( t2 ) ) if t2.f( i ) == t2.f( i ) ]
		t2_to_interpolate = t2.extract( not_nan )
	
		return( 
				interpolation( t1_to_interpolate , delta_t ) ,
				interpolation( t2_to_interpolate , delta_t )
				)

	def cc( input_t1 , input_t2 ):
		
		"""
		cc( input_t1 , input_t2 ) returns the time lag between the trajectory input_t1 and the trajectory input_t2,
		computed from the cross correlation of the fluorescence intensities of the two trajectories. 
		The trajectory input_t2 will be aligned in time to input_t1 by adding the output of cc to input_t2.t()
		"""

		t1 = cp.deepcopy( input_t1 )
		t2 = cp.deepcopy( input_t2 )

		if t1.annotations()[ 'delta_t' ] != t2.annotations()[ 'delta_t' ] :
			raise AttributeError('The two trajectories have different \'delta_t\' ') 
		else: 
			delta_t = t1.annotations()[ 'delta_t' ]
		
		#extend t1 to be as long as to include the equivalent
		#of t2 lifetime as NA before and after it:

		t1.start( t1.start() - t2.lifetime() )
		t1.end( t1.end() + t2.lifetime() )
		
		#align the two trajectories to the same start point
		lag0 = t1.start() - t2.start()
		t2.input_values( 't' , t2.t() + lag0 )

		output = []
		while t2.end() <= t1.end() :

			#because of rounding errors I cannot use:
			#f1 = [ t1.f( i ) for i in range( len( t1 ) ) if ( t1.t( i ) >= t2.start() ) & ( t1.t( i ) <= t2.end() ) ] 
			#but the following, where instead of greater than... I use >< delta_t / 2
			f1 = [ t1.f( i ) for i in range( len( t1 ) ) if ( t1.t( i ) - t2.start() > - delta_t / 2 ) & ( t1.t( i ) - t2.end() < delta_t / 2 ) ] 
			
			if len( f1 ) != len( t2 ) : raise IndexError( "There is a problem with the selection of t1 fluorescence intensities and t2 length in the cross-correlation function cc. The lengths do not match.")

			output.append( 
					sum( [ f1[ i ] * t2.f( i ) for i in range( len( t2 ) ) if ( f1[ i ] == f1[ i ] ) & ( t2.f( i ) == t2.f( i ) ) ] )
					)
			
			t2.lag( 1 )

		return( lag0 + output.index( max( output ) ) * t1.annotations()[ 'delta_t' ] )

	def unify_start_and_end( t1 , t2 ):
	
		"""
		Uniform the start and the end of two trajectories that overlap
		in time, so that the overlapping time points can be used to compute the
		rotation and translation that aligns the two trajectories together.
		"""
		
		if t1.annotations()[ 'delta_t' ] != t2.annotations()[ 'delta_t' ] : 
			raise AttributeError('The trajectoires inputed in unify_start_and_end \
					have different delta_t')
		if t1.start() >= t2.end() : 
			raise AttributeError('The trajectory t1 inputed in unify_start_and_end \
					starts after the trajectory t2. The two trajectories must significantly overlap')
		if t2.start() >= t1.end() : 
			raise AttributeError('The trajectory t2 inputed in unify_start_and_end \
					starts after the trajectory t2. The two trajectories must significantly overlap')
	
		if t1.start() < t2.start() :
			t1.start( t2.start() )
		else :
			t2.start( t1.start() )
		if t1.end() < t2.end() :
			t2.end( t1.end() )
		else :
			t1.end( t2.end() )

		return()

	def R( angle ) : 

		return( np.matrix( [[ np.cos( angle ) , - np.sin( angle ) ] , [ np.sin( angle ) , np.cos( angle ) ]] , dtype = 'float64' ) )
	
	#----------------------------------------------------------------

	t1 = Traj()
	t1.load( path_target )

	t2 = Traj()
	t2.load( path_reference )

	#average trajectories are centered on their center of mass to minimise inaccuracies
	#that can derive from the approximation of the rotation and traslation
	#(see Picco et al. 2015, Material and Methods section for further reference).
	#Ideally, rotations should be computer with quaternions.
	t1_center_of_mass = t1.center_mass()
	t1.translate( - t1_center_of_mass )
	t2.translate( - t2.center_mass() )

	
	l = len( ch1 )
	
	#control that the dataset of loaded trajectories is complete
	if l != len( ch2 ) : raise IndexError( 'The number of trajectories for ch1 and for ch2 differ.' )

	#define the dictionary where the transformations will be stored
	T = { 'angle' : [] , 'translation' : [] , 'lag' : [] }

	#compute the transformations that align t1 and t2 together.
	#l = 6 #DEBUG
	for i in range( l ) :

		print( "Align " + path_target + " to " + ch1[ i ].annotations( 'file' ) + " and " + path_reference + " to " + ch2[ i ].annotations( 'file' ) ) 

		#spline the trajectories, to reduce the noise
		spline_t1 , spline_ch1 = spline( t1 , ch1[ i ] )
		spline_t2 , spline_ch2 = spline( t2 , ch2[ i ] )

		#lag t1
		ch1_lag = cc( spline_t1 , spline_ch1 )
		spline_ch1.input_values( 't' , spline_ch1.t() + ch1_lag )
		#lag t2
		ch2_lag = cc( spline_t2 , spline_ch2 )
		spline_ch2.input_values( 't' , spline_ch2.t() + ch2_lag )

		#unify the start and the end of the trajectory splines that are paired to compute the rotation and translation.
		unify_start_and_end( spline_t1 , spline_ch1 )
		unify_start_and_end( spline_t2 , spline_ch2 )
	
		#NOTE: the weight used in Picco et al., 2015 is slightly different. To use the same weight one should replace spline_t1.f() with spline_t1.f() / ( spline_t1.coord_err()[ 0 ] * spline_t1.coord_err()[ 1 ] )
		align_ch1_to_t1 = MSD( spline_t1 , spline_ch1 ) 
		align_ch2_to_t2 = MSD( spline_t2 , spline_ch2 )

		#the tranformation we need to align t1 to t2 will be the transformation that align ch2 to t2 and the 
		#inverted transformation that aligns ch1 to t1.
		#
		# R_2 @ R_1^{-1} @ ( t1 - t1.center_mass() ) + R_2 @ ( ch1.center_mass() - ch2.center_mass() ) + t2.center_mass()
		#
		# As the mean in MSD is weighted (see MSD in trajalign/average.py) the equation becomes
		#
		# R_2 @ R_1^{-1} @ ( t1 - align_ch1_to_t1[ 'rc' ] ) + R_2 @ ( align_ch1_to_t1[ 'lc' ] - align_ch2_to_t2[ 'lc' ] ) + align_ch2_to_t2[ 'rc' ] 
		#
		# where align_ch1_to_t1[ 'rc' ], align_ch1_to_t1[ 'lc' ], align_ch2_to_t2[ 'rc' ] and align_ch2_to_t2[ 'lc' ] are 
		#the estimates of the center of masses with the weight mean convention used in MSD.
		#NOTE: in eLife, the center of mass of t1 that was used was the geometrical center 
		#of mass, t1.center_mass(), and not the approximation of the center of mass that best 
		#align t1 and ch1, given the weight convention in MSD.


		#compute the angle as the atan2 of the sin( align_ch2_to_t2[ 'angle' ] - align_ch1_to_t1[ 'angle' ] ) 
		#and cos( align_ch2_to_t2[ 'angle' ] - align_ch1_to_t1[ 'angle' ] ) 
		a = np.sin( align_ch2_to_t2[ 'angle' ] ) * np.cos( align_ch1_to_t1[ 'angle' ] ) -  np.cos( align_ch2_to_t2[ 'angle' ] ) * np.sin( align_ch1_to_t1[ 'angle' ] )  
		b = np.cos( align_ch2_to_t2[ 'angle' ] ) * np.cos( align_ch1_to_t1[ 'angle' ] ) +  np.sin( align_ch2_to_t2[ 'angle' ] ) * np.sin( align_ch1_to_t1[ 'angle' ] )  
		T[ 'angle' ].append( np.arctan2( a , b ) )
		#Using sin, cos and arctan avoids having angles as angle + 2 * k * pi with k > 0.  
		
		T[ 'translation' ].append( np.array( 
				- R( T[ 'angle' ][ -1 ] ) @ align_ch1_to_t1[ 'rc' ]\
						+ R( align_ch2_to_t2[ 'angle' ] ) @ ( align_ch1_to_t1[ 'lc' ] - align_ch2_to_t2[ 'lc' ] )\
						+ align_ch2_to_t2[ 'rc' ]
				)[ 0 ] ) #the [ 0 ] is beacuse otherwise it would be [[ x , y ]] instead of [ x , y ]
		# note that the translation is done slightly differently than as 
		# in Picco et al, 2015. As in Picco et al, 2015 
		#	- R( T[ 'angle' ][ -1 ] ) @ align_ch1_to_t1[ 'rc' ]
		# should be 
		#	- R( T[ 'angle' ][ -1 ] ) @ t1.center_mass()
		
		#lag
		T[ 'lag' ].append( ch2_lag - ch1_lag )
	
	#compute the median and the MAD of the transformations
	T_median = { 
			'angle' : np.median( T[ 'angle' ] ) ,
			'angle_MAD' : nanMAD( T[ 'angle' ] ) / np.sqrt( l ) ,
			'translation' : [
				np.median( [ T[ 'translation' ][ i ][ 0 ] for i in range( l ) ] ) ,
				np.median( [ T[ 'translation' ][ i ][ 1 ] for i in range( l ) ] )
				] ,
			'translation_MAD' : [
				nanMAD( [ T[ 'translation' ][ i ][ 0 ] for i in range( l ) ] ) / np.sqrt( l ),
				nanMAD( [ T[ 'translation' ][ i ][ 1 ] for i in range( l ) ] ) / np.sqrt( l ) 
				] ,
			'lag' : np.median( T[ 'lag' ] ) , 
			'lag_MAD' : nanMAD( T[ 'lag' ] ) ,
			'n' : l
			}

	t1.rotate( T_median[ 'angle' ] , 
			angle_err = T_median[ 'angle_MAD' ]
			)
	t1.translate( T_median[ 'translation' ] , 
			v_err = ( T_median[ 'translation_MAD' ][ 0 ] , T_median[ 'translation_MAD' ][ 1 ] )
			)
	t1.input_values( 't' , t1.t() + T_median[ 'lag' ] )

	dot_positions = [ i for i in range(len( path_target )) if path_target[i] == '.' ]
	file_ending = dot_positions[ len(dot_positions) - 1 ] #there could be more than one dot in the file name. Pick the last.
	file_name =  path_target[ 0 : file_ending ] + '_aligned' + path_target[ file_ending : len( path_target ) ]

	# annotations
	t1.annotations( 'aligned_to' , str( path_reference ) )
	t1.annotations( 'original_file' , str( path_target ) )
	t1.annotations( 'alignment_angle' , str( T_median[ 'angle' ] ) + ' rad' )
	t1.annotations( 'alignment_angle_MAD' , str( T_median[ 'angle_MAD' ] ) + ' rad' )
	t1.annotations( 'alignment_translation' , str( T_median[ 'translation' ] ) + ' ' + t1.annotations()[ 'coord_unit' ] )
	t1.annotations( 'alignment_translation_MAD' , str( T_median[ 'translation_MAD' ] ) + ' ' + t1.annotations()[ 'coord_unit' ] )
	t1.annotations( 'alignment_lag' , str( T_median[ 'lag' ] ) + ' ' + t1.annotations()[ 't_unit' ] )
	t1.annotations( 'alignment_lag_MAD' , str( T_median[ 'lag_MAD' ] ) + ' ' + t1.annotations()[ 't_unit' ] )

	t1.save( file_name )

	print( 'The trajectory aligned to ' + path_reference + ' has been saved as ' + file_name )

